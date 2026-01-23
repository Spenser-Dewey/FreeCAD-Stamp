'''Creates the wires and part objects'''

import FreeCAD
import Mesh
import math

import lithophane_utils
from utils.resource_utils import iconPath
from boolean_mesh import BooleanMesh
from boolean_mesh import ViewProviderBooleanMesh
from create_geometry_base import CreateGeometryBase


class ProcessingParameters(object):
    def __init__(self, image):
        self.image = image
        self.radius = min(image.length(), image.width()) / 2
        self.center = FreeCAD.Vector(image.length() / 2, image.width() / 2, 0)

        self.stamp = None
        self.imagePlane = None
        self.blockBase = None
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
                ('Image Base', self.makeBlockBase),
                ('Bottom Plane', self.createBottomCircle),
                ('Merge Meshes', self.mergeMeshes),
                ('Optimize Mesh', self.optimizeMesh)]

    def extractBaseMesh(self, obj, processingParameters):
        return processingParameters.stamp

    def makeImagePlane(self, obj, image):
        processingParameters = ProcessingParameters(image)
        lines = processingParameters.image.lines
        center = processingParameters.center
        radius = processingParameters.radius

        facets = []

        for lineNumber, actualLine in enumerate(lines):
            if lineNumber == len(lines) - 1:
                break

            nextLine = lines[lineNumber + 1]

            for rowNumber, actualPoint in enumerate(actualLine):
                if rowNumber == len(actualLine) - 1:
                    break

                bottomLeft = actualPoint
                
                if center.distanceToPoint(bottomLeft) > radius:
                    continue

                bottomRight = actualLine[rowNumber + 1] 
                topRight = nextLine[rowNumber + 1]  
                topLeft = nextLine[rowNumber]

                facets.extend([bottomLeft, bottomRight, topLeft])
                facets.extend([bottomRight, topRight, topLeft])

        processingParameters.imagePlane = Mesh.Mesh(facets)

        return processingParameters

    def makeBlockBase(self, obj, processingParameters):
        center = processingParameters.center
        radius = processingParameters.radius
        base_height = processingParameters.image.Object.BaseHeight.Value
        
        facets = []
        
        for i in range(360):
            angle1 = math.radians(i)
            angle2 = math.radians((i + 1) % 360)

            p1_bottom = center + FreeCAD.Vector(radius * math.cos(angle1), radius * math.sin(angle1), 0)
            p2_bottom = center + FreeCAD.Vector(radius * math.cos(angle2), radius * math.sin(angle2), 0)
            
            p1_top = FreeCAD.Vector(p1_bottom.x, p1_bottom.y, base_height)
            p2_top = FreeCAD.Vector(p2_bottom.x, p2_bottom.y, base_height)

            facets.extend([p1_bottom, p2_bottom, p2_top])
            facets.extend([p2_top, p1_top, p1_bottom])

        processingParameters.blockBase = Mesh.Mesh(facets)
        return processingParameters


    def createBottomCircle(self, obj, processingParameters):
        center = processingParameters.center
        radius = processingParameters.radius

        facets = []
        
        center_point = lithophane_utils.vectorAtGround(center)

        for i in range(360):
            angle1 = math.radians(i)
            angle2 = math.radians((i + 1) % 360)
            
            p1 = center + FreeCAD.Vector(radius * math.cos(angle1), radius * math.sin(angle1), 0)
            p2 = center + FreeCAD.Vector(radius * math.cos(angle2), radius * math.sin(angle2), 0)
            
            bottomLeft = lithophane_utils.vectorAtGround(p1)
            bottomRight = lithophane_utils.vectorAtGround(p2)
            
            facets.extend([center_point, bottomLeft, bottomRight])

        processingParameters.bottomCircle = Mesh.Mesh(facets)

        return processingParameters

    def mergeMeshes(self, obj, processingParameters):
        processingParameters.stamp = Mesh.Mesh()
        processingParameters.stamp.addMesh(processingParameters.imagePlane)
        processingParameters.stamp.addMesh(processingParameters.blockBase)
        processingParameters.stamp.addMesh(processingParameters.bottomCircle)

        return processingParameters

    def optimizeMesh(self, obj, processingParameters):
        processingParameters.stamp.removeDuplicatedPoints()
        processingParameters.stamp.harmonizeNormals()

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
