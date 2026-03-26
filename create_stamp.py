'''Creates the wires and part objects'''

import FreeCAD
import Mesh
import math

import lithophane_utils
from utils.resource_utils import iconPath
from boolean_mesh import BooleanMesh
from boolean_mesh import ViewProviderBooleanMesh
from create_geometry_base import CreateGeometryBase
from utils import geometry_utils


def _in_circle(point, center, radius):
    dx = point.x - center.x
    dy = point.y - center.y
    return dx * dx + dy * dy <= radius * radius


def _height_at(lines, x, y, pixel_size):
    """Nearest-neighbour height lookup into the lines grid."""
    col = int(round(x / pixel_size))
    row = int(round(y / pixel_size))
    col = max(0, min(col, len(lines[0]) - 1))
    row = max(0, min(row, len(lines) - 1))
    return lines[row][col].z


class ProcessingParameters(object):
    def __init__(self, image):
        self.image = image
        self.radius = min(image.length(), image.width()) / 2
        self.center = FreeCAD.Vector(image.length() / 2, image.width() / 2, 0)

        self.stamp = None
        self.imagePlane = None
        self.stampWalls = None
        self.bottomCircle = None


class StampLithophane(BooleanMesh):
    def __init__(self, obj):
        super().__init__(obj)

    def getDescription(self):
        return 'CreateStamp'
    
    def getIcon(self):
        return iconPath('CreateStamp.svg')

    def getBaseProcessingSteps(self, obj):
        return [('Image Plane', self.makeImagePlane),
                ('Image Base', self.makeStampCylinder),
                ('Bottom Plane', self.createBottomCircle),
                ('Merge Meshes', self.mergeMeshes),
                ('Optimize Mesh', self.optimizeMesh)]

    def extractBaseMesh(self, obj, processingParameters):
        return processingParameters.stamp

    def makeImagePlane(self, obj, image):
        processingParameters = ProcessingParameters(image)
        lines = processingParameters.image.lines
        base_height = obj.LithophaneImage.BaseHeight.Value
        center = processingParameters.center
        radius = processingParameters.radius
        pixel_size = lines[0][1].x

        facets = []

        # Top surface: only emit quads fully within the circle
        for lineNumber in range(len(lines) - 1):
            actualLine = lines[lineNumber]
            nextLine = lines[lineNumber + 1]
            for rowNumber in range(len(actualLine) - 1):
                p00 = actualLine[rowNumber]
                p10 = actualLine[rowNumber + 1]
                p01 = nextLine[rowNumber]
                p11 = nextLine[rowNumber + 1]
                if all(_in_circle(p, center, radius) for p in (p00, p10, p01, p11)):
                    facets.extend([p00, p10, p01])
                    facets.extend([p10, p11, p01])

        # Rim wall: connects the circle boundary from lithophane height down to
        # base_height, sealing the gap between the cropped top surface and the
        # cylinder wall top edge. Uses nearest-neighbour lookup for height.
        for i in range(360):
            p1_xy = geometry_utils.pointOnCircle(radius, i)
            p2_xy = geometry_utils.pointOnCircle(radius, (i + 1) % 360)

            z1 = _height_at(lines, center.x + p1_xy[0], center.y + p1_xy[1], pixel_size)
            z2 = _height_at(lines, center.x + p2_xy[0], center.y + p2_xy[1], pixel_size)

            rim_top1 = center + FreeCAD.Vector(p1_xy[0], p1_xy[1], z1)
            rim_top2 = center + FreeCAD.Vector(p2_xy[0], p2_xy[1], z2)
            rim_bot1 = center + FreeCAD.Vector(p1_xy[0], p1_xy[1], base_height)
            rim_bot2 = center + FreeCAD.Vector(p2_xy[0], p2_xy[1], base_height)

            # Same winding pattern as makeStampCylinder
            facets.extend([rim_bot1, rim_bot2, rim_top2])
            facets.extend([rim_top2, rim_top1, rim_bot1])

        processingParameters.imagePlane = Mesh.Mesh(facets)
        return processingParameters

    def makeStampCylinder(self, obj, processingParameters):
        center = processingParameters.center
        radius = processingParameters.radius
        base_height = obj.LithophaneImage.BaseHeight.Value

        facets = []

        # Side walls of the cylindrical base, from Z=0 to Z=base_height
        for i in range(360):
            p1 = geometry_utils.pointOnCircle(radius, i)
            p2 = geometry_utils.pointOnCircle(radius, (i + 1) % 360)

            p1_bottom = center + FreeCAD.Vector(p1[0], p1[1], 0)
            p2_bottom = center + FreeCAD.Vector(p2[0], p2[1], 0)
            p1_top = center + FreeCAD.Vector(p1[0], p1[1], base_height)
            p2_top = center + FreeCAD.Vector(p2[0], p2[1], base_height)

            # Two triangles forming a quad for the current slice of the circumference
            facets.extend([p1_bottom, p2_bottom, p2_top])
            facets.extend([p2_top, p1_top, p1_bottom])

        processingParameters.stampWalls = Mesh.Mesh(facets)
        return processingParameters


    def createBottomCircle(self, obj, processingParameters):
        center = processingParameters.center
        radius = processingParameters.radius

        facets = []
        
        center_point = FreeCAD.Vector(center.x, center.y, 0)

        for i in range(360):
            p1 = geometry_utils.pointOnCircle(radius, i)
            p2 = geometry_utils.pointOnCircle(radius, (i + 1) % 360)

            v1 = center + FreeCAD.Vector(p1[0], p1[1], 0)
            v2 = center + FreeCAD.Vector(p2[0], p2[1], 0)

            facets.extend([center_point, v2, v1])  # reversed winding: normal faces -Z (outward)

        processingParameters.bottomCircle = Mesh.Mesh(facets)

        return processingParameters

    def mergeMeshes(self, obj, processingParameters):
        processingParameters.stamp = Mesh.Mesh()
        processingParameters.stamp.addMesh(processingParameters.imagePlane)
        processingParameters.stamp.addMesh(processingParameters.stampWalls)
        processingParameters.stamp.addMesh(processingParameters.bottomCircle)

        return processingParameters

    def optimizeMesh(self, obj, processingParameters):
        processingParameters.stamp.removeDuplicatedPoints()
        processingParameters.stamp.harmonizeNormals()

        # Add mesh integrity checks here
        FreeCAD.Console.PrintMessage("\n--- Mesh Diagnostics after optimization ---\
")
        FreeCAD.Console.PrintMessage(f"Number of points: {processingParameters.stamp.Points.__len__()}\
")
        FreeCAD.Console.PrintMessage(f"Number of facets: {processingParameters.stamp.Facets.__len__()}\
")
        
        # Check for common mesh errors
        if processingParameters.stamp.hasNonManifolds():
            FreeCAD.Console.PrintError("Mesh has non-manifold edges!\n")
        # if processingParameters.stamp.hasInvertedNormals():
            # FreeCAD.Console.PrintError("Mesh has inverted normals!\n")
        processingParameters.stamp.fixSelfIntersections()
            # FreeCAD.Console.PrintError("Mesh is self-intersecting!\n")
        
        FreeCAD.Console.PrintMessage("--- End Mesh Diagnostics ---\
")

        return processingParameters


class CreateStampCommand(CreateGeometryBase):
    toolbarName = 'Image_Tools'
    commandName = 'Create_Stamp'

    def GetResources(self):
        return {'MenuText': "Create Stamp",
                'ToolTip': "Creates the geometry of the selected Lithophane Image in the shape of a stamp",
                'Pixmap': iconPath('CreateStamp.svg')}
    
    def createGeometryInstance(self, documentObject, imageLabel):
        obj = FreeCAD.ActiveDocument.addObject(
            "App::FeaturePython", imageLabel + '_Mesh')

        StampLithophane(obj)
        ViewProviderBooleanMesh(obj.ViewObject)

        obj.LithophaneImage = documentObject


if __name__ == "__main__":
    command = CreateStampCommand()

    if command.IsActive():
        command.Activated()
    else:
        import utils.qtutils as qtutils
        qtutils.showInfo("No open Document", "There is no open document")
else:
    import toolbars
    toolbars.toolbarManager.registerCommand(CreateStampCommand())