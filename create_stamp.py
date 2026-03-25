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

        facets = []

        # Top surface (varying height lithophane)
        # for lineNumber in range(len(lines) - 1):
            # actualLine = lines[lineNumber]
            # nextLine = lines[lineNumber + 1]

            # for rowNumber in range(len(actualLine) - 1):
                # p00_top = actualLine[rowNumber]
                # p10_top = actualLine[rowNumber + 1]
                # p01_top = nextLine[rowNumber]
                # p11_top = nextLine[rowNumber + 1]

                # facets.extend([p00_top, p10_top, p01_top])
                # facets.extend([p10_top, p11_top, p01_top])

        # Four outer walls connecting the top lithophane surface to base_height
        # These walls will connect to the `stampWalls`
        
        # 1. Wall along min_y edge
        # for i in range(len(lines[0]) - 1):
            # p1_top = lines[0][i]
            # p2_top = lines[0][i+1]
            # p1_bottom = FreeCAD.Vector(p1_top.x, p1_top.y, base_height)
            # p2_bottom = FreeCAD.Vector(p2_top.x, p2_top.y, base_height)
            # facets.extend([p1_top, p2_top, p2_bottom])
            # facets.extend([p2_bottom, p1_bottom, p1_top])

        # 2. Wall along max_y edge
        # for i in range(len(lines[-1]) - 1):
            # p1_top = lines[-1][i]
            # p2_top = lines[-1][i+1]
            # p1_bottom = FreeCAD.Vector(p1_top.x, p1_top.y, base_height)
            # p2_bottom = FreeCAD.Vector(p2_top.x, p2_top.y, base_height)
            # facets.extend([p1_top, p1_bottom, p2_bottom]) # Reversed winding for external normal
            # facets.extend([p2_bottom, p2_top, p1_top]) # Reversed winding for external normal

        # 3. Wall along min_x edge
        # for i in range(len(lines) - 1):
            # p1_top = lines[i][0]
            # p2_top = lines[i+1][0]
            # p1_bottom = FreeCAD.Vector(p1_top.x, p1_top.y, base_height)
            # p2_bottom = FreeCAD.Vector(p2_top.x, p2_top.y, base_height)
            # facets.extend([p1_top, p1_bottom, p2_bottom]) # Reversed winding
            # facets.extend([p2_bottom, p2_top, p1_top]) # Reversed winding

        # 4. Wall along max_x edge
        # for i in range(len(lines) - 1):
            # p1_top = lines[i][-1]
            # p2_top = lines[i+1][-1]
            # p1_bottom = FreeCAD.Vector(p1_top.x, p1_top.y, base_height)
            # p2_bottom = FreeCAD.Vector(p2_top.x, p2_top.y, base_height)
            # facets.extend([p1_top, p2_top, p2_bottom])
            # facets.extend([p2_bottom, p1_bottom, p1_top])
            
        center_point = lithophane_utils.vectorAtGround(processingParameters.center)
        radius = processingParameters.radius
        for i in range(360):
            angle1 = math.radians(i)
            angle2 = math.radians((i + 1) % 360)
            
            p1 = geometry_utils.pointOnCircle(radius, angle1)
            p2 = geometry_utils.pointOnCircle(radius, angle2)
            
            bottomLeft = FreeCAD.Vector(p1[0], p1[1], base_height)
            bottomRight = FreeCAD.Vector(p2[0], p1[1], base_height)
            
            facets.extend([center_point, bottomLeft, bottomRight])
        processingParameters.imagePlane = Mesh.Mesh(facets)

        return processingParameters

    def makeStampCylinder(self, obj, processingParameters):
        center = processingParameters.center
        radius = processingParameters.radius
        base_height = obj.LithophaneImage.BaseHeight.Value

        facets = []

        # Side walls of the cylindrical base, from Z=0 to Z=base_height
        for i in range(360):
            angle1 = math.radians(i)
            angle2 = math.radians((i + 1) % 360)

            p1 = geometry_utils.pointOnCircle(processingParameters.radius, angle1)
            p2 = geometry_utils.pointOnCircle(processingParameters.radius, angle2)

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
        
        center_point = lithophane_utils.vectorAtGround(center) # Center at Z=0

        for i in range(360):
            angle1 = math.radians(i)
            angle2 = math.radians((i + 1) % 360)
            
            p1 = geometry_utils.pointOnCircle(radius, angle1)
            p2 = geometry_utils.pointOnCircle(radius, angle2)
            
            bottomLeft = FreeCAD.Vector(p1[0], p1[1], 0)
            bottomRight = FreeCAD.Vector(p2[0], p2[1], 0)
            
            facets.extend([center_point, bottomLeft, bottomRight])

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
        if processingParameters.stamp.isSelfIntersecting():
            FreeCAD.Console.PrintError("Mesh is self-intersecting!\n")
        
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