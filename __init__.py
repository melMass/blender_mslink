# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####
#
# The Megascans LiveLink plugin for Blender is an add-on that lets
# you instantly import assets with their shader setup with one click only.
#
# Because it relies on some of the latest 2.80 features, this plugin is currently
# only available for Blender 2.80 and forward.
#
# You are free to modify, add features or tweak this add-on as you see fit, and
# don't hesitate to send us some feedback if you've done something cool with it.
#
# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####

import bpy, threading, os, time, json, socket

globals()['Megascans_DataSet'] = None

bl_info = {
    "name": "Megascans LiveLink",
    "description": "Connects Blender to Quixel Bridge for one-click imports with shader setup and geometry",
    "author": "Quixel",
    "version": (2, 2),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart.html",
    "tracker_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart#release_notes",
    "support": "COMMUNITY",
    "category": "Import-Export"
}


# MS_Init_ImportProcess is the main asset import class.
# This class is invoked whenever a new asset is set from Bridge.

class MS_Init_ImportProcess():

    def __init__(self):
    # This initialization method create the data structure to process our assets
    # later on in the initImportProcess method. The method loops on all assets
    # that have been sent by Bridge.

        print("Initialized import class...")
        try:
            # Check if there's any incoming data
            if globals()['Megascans_DataSet'] != None:
                self.json_Array = json.loads(globals()['Megascans_DataSet'])

                # Start looping over each asset in the self.json_Array list
                for js in self.json_Array:

                    self.json_data = js

                    self.selectedObjects = []
                    
                    self.IOR = 1.45
                    self.assetType = self.json_data["type"]
                    self.assetPath = self.json_data["path"]
                    self.assetID = self.json_data["id"]
                    self.isMetal = bool(self.json_data["category"] == "Metal")
                    # Workflow setup.
                    self.isHighPoly = bool(self.json_data["activeLOD"] == "high")
                    self.activeLOD = self.json_data["activeLOD"]
                    self.minLOD = self.json_data["minLOD"]
                    self.RenderEngine = bpy.context.scene.render.engine.lower() # Get the current render engine. i.e. blender_eevee or cycles
                    self.Workflow = self.json_data.get('pbrWorkflow', 'specular')
                    self.DisplacementSetup = 'regular'
                    self.isCycles = bool(self.RenderEngine == 'cycles')
                    self.isScatterAsset = self.CheckScatterAsset()
                    self.textureList = []
                    self.isBillboard = self.CheckIsBillboard()

                    if (self.isCycles):
                        if(bpy.context.scene.cycles.feature_set == 'EXPERIMENTAL'):
                            self.DisplacementSetup = 'adaptive'


                    baseTextures = ["albedo", "diffuse", "displacement", "normal", "roughness",
                                    "specular", "normalbump", "ao", "opacity",
                                    "translucency", "gloss", "metalness", "bump", "fuzz"]
                    
                    texturesObjectName = "components"
                    if(self.isBillboard):
                        texturesObjectName = "components"

                    # Create a list of tuples of all the textures maps available.
                    # This tuple is composed of (textureFormat, textureMapType, texturePath)
                    for obj in self.json_data[texturesObjectName]:
                        if obj["type"] in baseTextures:
                            if(obj["type"] == "displacement") and self.DisplacementSetup == 'adaptive':
                                #Do the EXR displacement thingy.
                                if (obj["format"] != "exr"):
                                    disp_path_recv = obj["path"]
                                    k = disp_path_recv.rfind(obj["format"]) # k is the last index for where the file format starts in the string.
                                    disp_path_exr = disp_path_recv[:k] + "exr" # we appead exr as file type to check if it exists.
                                    if(os.path.isfile(disp_path_exr)):
                                        self.textureList.append(("exr", obj["type"], disp_path_exr)) # if EXR displacement exists we can safely use it.
                                    else:
                                        self.textureList.append( (obj["format"], obj["type"], obj["path"]))
                                else:
                                    self.textureList.append( (obj["format"], obj["type"], obj["path"]))
                            else:
                                self.textureList.append( (obj["format"], obj["type"], obj["path"]) )

                    # Create a tuple list of all the 3d meshes  available.
                    # This tuple is composed of (meshFormat, meshPath)
                    self.geometryList = [(obj["format"], obj["path"]) for obj in self.json_data["meshList"]]

                    # Create name of our asset. Multiple conditions are set here
                    # in order to make sure the asset actually has a name and that the name
                    # is short enough for us to use it. We compose a name with the ID otherwise.
                    if "name" in self.json_data.keys():
                        self.assetName = self.json_data["name"].replace(" ", "_")
                    else:
                        self.assetName = os.path.basename(self.json_data["path"]).replace(" ", "_")
                    if len(self.assetName.split("_")) > 2:
                        self.assetName = "_".join(self.assetName.split("_")[:-1])

                    self.materialName = self.assetName + '_' + self.assetID

                    # Initialize the import method to start building our shader and import our geometry
                    self.initImportProcess()
                    print("Imported asset from " + self.assetName + " Quixel Bridge")

        except Exception as e:
            print( "Megascans LiveLink Error initializing the import process. Error: ", str(e) )


        globals()['Megascans_DataSet'] = None
    # this method is used to import the geometry and create the material setup.
    def initImportProcess(self):
        try:
            if len(self.textureList) >= 1:

                self.ImportGeometry()
                mat = self.CreateMaterial()
                self.ApplyMaterialToGeometry(mat)
                if(self.isScatterAsset and len(self.selectedObjects) > 1):
                    self.ScatterAssetSetup()

                if self.assetType == "3d":
                    self.SetupMaterial3DAsset(mat)
                elif self.assetType == "3dplant":
                    self.SetupMaterial3DPlant(mat)
                else:
                    if self.isMetal:
                        self.SetupMaterial2DMetal(mat)
                    else:
                        self.SetupMaterial2D(mat)

        except Exception as e:
            print( "Megascans LiveLink Error while importing textures/geometry or setting up material. Error: ", str(e) )

    def ImportGeometry(self):
        try:
            # Import geometry
            if len(self.geometryList) >= 1:
                for obj in self.geometryList:
                    meshPath = obj[1]
                    meshFormat = obj[0]

                    if meshFormat.lower() == "fbx":
                        bpy.ops.import_scene.fbx(filepath=meshPath)
                        # get selected objects
                        obj_objects = [ o for o in bpy.context.scene.objects if o.select_get() ]
                        self.selectedObjects += obj_objects

                    elif meshFormat.lower() == "obj":
                        bpy.ops.import_scene.obj(filepath=meshPath)
                        # get selected objects
                        obj_objects = [ o for o in bpy.context.scene.objects if o.select_get() ]
                        self.selectedObjects += obj_objects

                    elif meshFormat.lower() == "abc" and False:
                        # self.dump(bpy.context)
                        # return
                        # for window in bpy.context.window_manager.windows:
                        #     for area in window.screen.areas:
                        # #for area in bpy.context.screen.areas:
                        #         if area.type == 'FILE_BROWSER' or area.type == 'OUTLINER':
                        #             override = bpy.context.copy()
                        #             override['area'] = area
                        #             bpy.ops.wm.alembic_import(override, filepath=meshPath, as_background_job=False)
                        #             break
                        # area = bpy.context.area
                        # old_type = area.type
                        # area.type = 'VIEW_3D'
                        bpy.ops.wm.alembic_import({}, filepath=meshPath, as_background_job=False)
                        # area.type = old_type
                        # get selected objects
                        obj_objects = [ o for o in bpy.context.scene.objects if o.select_get() ]
                        self.selectedObjects += obj_objects
        except Exception as e:
            print( "Megascans LiveLink Error while importing textures/geometry or setting up material. Error: ", str(e) )

    def dump(self, obj):
        for attr in dir(obj):
            print("obj.%s = %r" % (attr, getattr(obj, attr)))

    def CreateMaterial(self):
        # Create material
        mat = (bpy.data.materials.get( self.materialName ) or bpy.data.materials.new( self.materialName ))
        mat.use_nodes = True
        return mat

    def ApplyMaterialToGeometry(self, mat):
        for obj in self.selectedObjects:
            # assign material to obj
            obj.active_material = mat

    def CheckScatterAsset(self):
        if('scatter' in self.json_data['categories'] or 'scatter' in self.json_data['tags']):
            return True
        return False

    def CheckIsBillboard(self):
        # Use billboard textures if importing the Billboard LOD.
        if(self.assetType == "3dplant"):
            if (self.activeLOD == self.minLOD):
                # print("It is billboard LOD.")
                return True
        return False

    def ScatterAssetSetup(self):
        # Create an empty object
        bpy.ops.object.empty_add(type='ARROWS')
        emptyRefList = [ o for o in bpy.context.scene.objects if o.select_get() and o not in self.selectedObjects ]
        for scatterParentObject in emptyRefList:
            scatterParentObject.name = self.assetID + "_" + self.assetName
            for obj in self.selectedObjects:
                obj.parent = scatterParentObject
            break

    # def AddModifiersToGeomtry(self, geo_list, mat):
    #     for obj in geo_list:
    #         # assign material to obj
    #         bpy.ops.object.modifier_add(type='SOLIDIFY')

    #Shader setups for different asset types
    def SetupMaterial2D (self, mat):
        print("Setting up material for 2D surface (non-metal)")

        nodes = mat.node_tree.nodes
        # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
        maps_ = [item[1] for item in self.textureList]
        parentName = "Principled BSDF"
        materialOutputName = "Material Output"

        colorSpaces = getColorspaces()

        mat.node_tree.nodes[parentName].distribution = 'MULTI_GGX'
        mat.node_tree.nodes[parentName].inputs[4].default_value = 1 if self.isMetal else 0 # Metallic value
        mat.node_tree.nodes[parentName].inputs[14].default_value = self.IOR

        if self.isCycles:
            # Create mapping node.
            mappingNode = nodes.new("ShaderNodeMapping")
            mappingNode.location = (-1950, 0)
            mappingNode.vector_type = 'TEXTURE'
            # Create texture coordinate node.
            texCoordNode = nodes.new("ShaderNodeTexCoord")
            texCoordNode.location = (-2150, -200)
            # Connect texCoordNode to the mappingNode
            mat.node_tree.links.new(mappingNode.inputs[0], texCoordNode.outputs[0])

        use_diffuse = True
        # Create the albedo x ao setup.
        if "albedo" in maps_:
            if "ao" in maps_:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                aoPath = [item[2] for item in self.textureList if item[1] == "ao"]
                if len(albedoPath) >= 1 and  len(aoPath) >= 1:
                    use_diffuse = False
                    #Add Color>MixRGB node, transform it in the node editor, change it's operation to Multiply and finally we colapse the node.
                    multiplyNode = nodes.new("ShaderNodeMixRGB")
                    multiplyNode.blend_type = 'MULTIPLY'
                    multiplyNode.location = (-250, 320)
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 460)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    #Import ao and ao node setup.
                    aoPath = aoPath[0].replace("\\", "/")
                    aoNode = nodes.new('ShaderNodeTexImage')
                    aoNode.location = (-640, 200)
                    aoNode.image = bpy.data.images.load(aoPath)
                    aoNode.show_texture = True
                    aoNode.image.colorspace_settings.name = colorSpaces[1]
                    # Conned albedo and ao node to the multiply node.
                    mat.node_tree.links.new(multiplyNode.inputs[1], albedoNode.outputs[0])
                    mat.node_tree.links.new(multiplyNode.inputs[2], aoNode.outputs[0])
                    # Connect multiply node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], multiplyNode.outputs[0])
                    # Add mapping node connection in order to support tiling
                    if self.isCycles:
                        mat.node_tree.links.new(albedoNode.inputs[0], mappingNode.outputs[0])
                        mat.node_tree.links.new(aoNode.inputs[0], mappingNode.outputs[0])
            else:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                if len(albedoPath) >= 1:
                    use_diffuse = False
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 420)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    # Connect albedo node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], albedoNode.outputs[0])
                    # Add mapping node connection in order to support tiling
                    if self.isCycles:
                        mat.node_tree.links.new(albedoNode.inputs[0], mappingNode.outputs[0])

        # Create the diffuse setup.
        if "diffuse" in maps_ and use_diffuse:
            diffusePath = [item[2] for item in self.textureList if item[1] == "diffuse"]
            if len(diffusePath) >= 1:
                # Import diffuse and diffuse node setup.
                diffusePath = diffusePath[0].replace("\\", "/")
                diffuseNode = nodes.new('ShaderNodeTexImage')
                diffuseNode.location = (-640, 420)
                diffuseNode.image = bpy.data.images.load(diffusePath)
                diffuseNode.show_texture = True
                diffuseNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect diffuse node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[0], diffuseNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(diffuseNode.inputs[0], mappingNode.outputs[0])
        
        use_metalness = True
        # Create the specular setup.
        if "specular" in maps_:
            specularPath = [item[2] for item in self.textureList if item[1] == "specular"]
            if len(specularPath) >= 1:
                use_metalness = False
                # Import specular and specular node setup.
                specularPath = specularPath[0].replace("\\", "/")
                specularNode = nodes.new('ShaderNodeTexImage')
                specularNode.location = (-1150, 200)
                specularNode.image = bpy.data.images.load(specularPath)
                specularNode.show_texture = True
                specularNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[5], specularNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(specularNode.inputs[0], mappingNode.outputs[0])

        # Create the metalness setup. Use metalness if specular is missing
        if "metalness" in maps_ and use_metalness:
            metalnessPath = [item[2] for item in self.textureList if item[1] == "metalness"]
            if len(metalnessPath) >= 1:
                # Import specular and specular node setup.
                metalnessPath = metalnessPath[0].replace("\\", "/")
                metalnessNode = nodes.new('ShaderNodeTexImage')
                metalnessNode.location = (-1150, 200)
                metalnessNode.image = bpy.data.images.load(metalnessPath)
                metalnessNode.show_texture = True
                metalnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[4], metalnessNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(metalnessNode.inputs[0], mappingNode.outputs[0])

        use_gloss = True
        # Create the roughness setup.
        if "roughness" in maps_:
            roughnessPath = [item[2] for item in self.textureList if item[1] == "roughness"]
            if len(roughnessPath) >= 1:
                use_gloss = False
                # Import roughness and roughness node setup.
                roughnessPath = roughnessPath[0].replace("\\", "/")
                roughnessNode = nodes.new('ShaderNodeTexImage')
                roughnessNode.location = (-1150, -60)
                roughnessNode.image = bpy.data.images.load(roughnessPath)
                roughnessNode.show_texture = True
                roughnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], roughnessNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(roughnessNode.inputs[0], mappingNode.outputs[0])
        
        # Create the gloss setup.
        if "gloss" in maps_ and use_gloss:
            glossPath = [item[2] for item in self.textureList if item[1] == "gloss"]
            if len(glossPath) >= 1:
                # Add vector>bump node
                invertNode = nodes.new("ShaderNodeInvert")
                invertNode.location = (-250, 68)
                # Import roughness and roughness node setup.
                glossPath = glossPath[0].replace("\\", "/")
                glossNode = nodes.new('ShaderNodeTexImage')
                glossNode.location = (-1150, -60)
                glossNode.image = bpy.data.images.load(glossPath)
                glossNode.show_texture = True
                glossNode.image.colorspace_settings.name = colorSpaces[1]
                # Add glossNode to invertNode connection
                mat.node_tree.links.new(invertNode.inputs[1], glossNode.outputs[0])
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], invertNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(glossNode.inputs[0], mappingNode.outputs[0])

        # Create the opacity setup.
        if "opacity" in maps_:
            opacityPath = [item[2] for item in self.textureList if item[1] == "opacity"]
            if len(opacityPath) >= 1:
                # Import opacity and opacity node setup.
                opacityPath = opacityPath[0].replace("\\", "/")
                opacityNode = nodes.new('ShaderNodeTexImage')
                opacityNode.location = (-1550, -160)
                opacityNode.image = bpy.data.images.load(opacityPath)
                opacityNode.show_texture = True
                opacityNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect opacity node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[18], opacityNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(opacityNode.inputs[0], mappingNode.outputs[0])

        # Create the translucency setup.
        if "translucency" in maps_:
            translucencyPath = [item[2] for item in self.textureList if item[1] == "translucency"]
            if len(translucencyPath) >= 1:
                # Import translucency and translucency node setup.
                translucencyPath = translucencyPath[0].replace("\\", "/")
                translucencyNode = nodes.new('ShaderNodeTexImage')
                translucencyNode.location = (-1550, -420)
                translucencyNode.image = bpy.data.images.load(translucencyPath)
                translucencyNode.show_texture = True
                translucencyNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect translucency node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[15], translucencyNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(translucencyNode.inputs[0], mappingNode.outputs[0])

        setup_normal = True
        # Create the normal + bump setup.
        if "normal" in maps_ and "bump" in maps_:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(normalPath) >= 1 and  len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -130)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-640, -400)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-1150, -580)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                mat.node_tree.links.new(bumpNode.inputs[3], normalNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(normalMapNode.inputs[0], mappingNode.outputs[0])
                    mat.node_tree.links.new(bumpMapNode.inputs[0], mappingNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "normal" in maps_ and setup_normal:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            if len(normalPath) >= 1:
                setup_normal = False
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-250, -170)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-640, -207)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add normalNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(normalMapNode.inputs[0], mappingNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "bump" in maps_ and setup_normal:
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -207)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(bumpMapNode.inputs[0], mappingNode.outputs[0])
    
        # Create the displacement setup.
        if "displacement" in maps_:
            if self.DisplacementSetup == "adaptive":
                displacementPath = [item[2] for item in self.textureList if item[1] == "displacement"]
                if len(displacementPath) >= 1:
                    # Add vector>displacement map node
                    displacementNode = nodes.new("ShaderNodeDisplacement")
                    displacementNode.location = (10, -400)
                    displacementNode.inputs[0].default_value = 0.1
                    displacementNode.inputs[1].default_value = 0
                    # Add converter>RGB Separator node
                    RGBSplitterNode = nodes.new("ShaderNodeSeparateRGB")
                    RGBSplitterNode.location = (-250, -499)
                    # Import normal map and normal map node setup.
                    displacementPath = displacementPath[0].replace("\\", "/")
                    displacementMapNode = nodes.new('ShaderNodeTexImage')
                    displacementMapNode.location = (-640, -740)
                    displacementMapNode.image = bpy.data.images.load(displacementPath)
                    displacementMapNode.show_texture = True
                    displacementMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add displacementMapNode to RGBSplitterNode connection
                    mat.node_tree.links.new(RGBSplitterNode.inputs[0], displacementMapNode.outputs[0])
                    # Add RGBSplitterNode to displacementNode connection
                    mat.node_tree.links.new(displacementNode.inputs[2], RGBSplitterNode.outputs[0])
                    # Add normalNode connection to the material output displacement node
                    mat.node_tree.links.new(nodes.get(materialOutputName).inputs[2], displacementNode.outputs[0])
                    mat.cycles.displacement_method = 'BOTH'
                    # Add mapping node connection in order to support tiling
                    if self.isCycles:
                        mat.node_tree.links.new(displacementMapNode.inputs[0], mappingNode.outputs[0])

            if self.DisplacementSetup == "regular":
                pass

        return

    def SetupMaterial2DMetal (self, mat):
        print("Setting up material for 2D surface (metal)")
        print("Setting up material for 2D surface (non-metal)")

        nodes = mat.node_tree.nodes
        # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
        maps_ = [item[1] for item in self.textureList]
        parentName = "Principled BSDF"
        materialOutputName = "Material Output"

        colorSpaces = getColorspaces()

        mat.node_tree.nodes[parentName].distribution = 'MULTI_GGX'
        mat.node_tree.nodes[parentName].inputs[4].default_value = 1 if self.isMetal else 0 # Metallic value
        mat.node_tree.nodes[parentName].inputs[14].default_value = self.IOR

        if self.isCycles:
            # Create mapping node.
            mappingNode = nodes.new("ShaderNodeMapping")
            mappingNode.location = (-1950, 0)
            mappingNode.vector_type = 'TEXTURE'
            # Create texture coordinate node.
            texCoordNode = nodes.new("ShaderNodeTexCoord")
            texCoordNode.location = (-2150, -200)
            # Connect texCoordNode to the mappingNode
            mat.node_tree.links.new(mappingNode.inputs[0], texCoordNode.outputs[0])

        use_diffuse = True
        # Create the albedo x ao setup.
        if "albedo" in maps_:
            albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
            if len(albedoPath) >= 1:
                use_diffuse = False
                #Import albedo and albedo node setup.
                albedoPath = albedoPath[0].replace("\\", "/")
                albedoNode = nodes.new('ShaderNodeTexImage')
                albedoNode.location = (-640, 420)
                albedoNode.image = bpy.data.images.load(albedoPath)
                albedoNode.show_texture = True
                albedoNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect albedo node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[0], albedoNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(albedoNode.inputs[0], mappingNode.outputs[0])

        use_metalness = True
        # Create the diffuse setup.
        if "diffuse" in maps_ and use_diffuse:
            diffusePath = [item[2] for item in self.textureList if item[1] == "diffuse"]
            if len(diffusePath) >= 1:
                use_metalness = False or "specular" not in maps_
                # Import diffuse and diffuse node setup.
                diffusePath = diffusePath[0].replace("\\", "/")
                diffuseNode = nodes.new('ShaderNodeTexImage')
                diffuseNode.location = (-640, 420)
                diffuseNode.image = bpy.data.images.load(diffusePath)
                diffuseNode.show_texture = True
                diffuseNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect diffuse node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[0], diffuseNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(diffuseNode.inputs[0], mappingNode.outputs[0])
        
        use_specular = True
        # Create the metalness setup. Use metalness if specular is missing
        if "metalness" in maps_ and use_metalness:
            metalnessPath = [item[2] for item in self.textureList if item[1] == "metalness"]
            if len(metalnessPath) >= 1:
                use_specular = False
                # Import specular and specular node setup.
                metalnessPath = metalnessPath[0].replace("\\", "/")
                metalnessNode = nodes.new('ShaderNodeTexImage')
                metalnessNode.location = (-1150, 200)
                metalnessNode.image = bpy.data.images.load(metalnessPath)
                metalnessNode.show_texture = True
                metalnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[4], metalnessNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(metalnessNode.inputs[0], mappingNode.outputs[0])

        # Create the specular setup.
        if "specular" in maps_ and use_specular:
            specularPath = [item[2] for item in self.textureList if item[1] == "specular"]
            if len(specularPath) >= 1:
                use_metalness = False
                # Import specular and specular node setup.
                specularPath = specularPath[0].replace("\\", "/")
                specularNode = nodes.new('ShaderNodeTexImage')
                specularNode.location = (-1150, 200)
                specularNode.image = bpy.data.images.load(specularPath)
                specularNode.show_texture = True
                specularNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[5], specularNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(specularNode.inputs[0], mappingNode.outputs[0])

        use_gloss = True
        # Create the roughness setup.
        if "roughness" in maps_:
            roughnessPath = [item[2] for item in self.textureList if item[1] == "roughness"]
            if len(roughnessPath) >= 1:
                use_gloss = False
                # Import roughness and roughness node setup.
                roughnessPath = roughnessPath[0].replace("\\", "/")
                roughnessNode = nodes.new('ShaderNodeTexImage')
                roughnessNode.location = (-1150, -60)
                roughnessNode.image = bpy.data.images.load(roughnessPath)
                roughnessNode.show_texture = True
                roughnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], roughnessNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(roughnessNode.inputs[0], mappingNode.outputs[0])
        
        # Create the gloss setup.
        if "gloss" in maps_ and use_gloss:
            glossPath = [item[2] for item in self.textureList if item[1] == "gloss"]
            if len(glossPath) >= 1:
                # Add vector>bump node
                invertNode = nodes.new("ShaderNodeInvert")
                invertNode.location = (-250, 68)
                # Import roughness and roughness node setup.
                glossPath = glossPath[0].replace("\\", "/")
                glossNode = nodes.new('ShaderNodeTexImage')
                glossNode.location = (-1150, -60)
                glossNode.image = bpy.data.images.load(glossPath)
                glossNode.show_texture = True
                glossNode.image.colorspace_settings.name = colorSpaces[1]
                # Add glossNode to invertNode connection
                mat.node_tree.links.new(invertNode.inputs[1], glossNode.outputs[0])
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], invertNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(glossNode.inputs[0], mappingNode.outputs[0])

        setup_normal = True
        # Create the normal + bump setup.
        if "normal" in maps_ and "bump" in maps_:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(normalPath) >= 1 and  len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -130)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-640, -400)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-1150, -580)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                mat.node_tree.links.new(bumpNode.inputs[3], normalNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(normalMapNode.inputs[0], mappingNode.outputs[0])
                    mat.node_tree.links.new(bumpMapNode.inputs[0], mappingNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "normal" in maps_ and setup_normal:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            if len(normalPath) >= 1:
                setup_normal = False
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-250, -170)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-640, -207)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add normalNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(normalMapNode.inputs[0], mappingNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "bump" in maps_ and setup_normal:
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -207)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
                # Add mapping node connection in order to support tiling
                if self.isCycles:
                    mat.node_tree.links.new(bumpMapNode.inputs[0], mappingNode.outputs[0])
    
        # Create the displacement setup.
        if "displacement" in maps_:
            if self.DisplacementSetup == "adaptive":
                displacementPath = [item[2] for item in self.textureList if item[1] == "displacement"]
                if len(displacementPath) >= 1:
                    # Add vector>displacement map node
                    displacementNode = nodes.new("ShaderNodeDisplacement")
                    displacementNode.location = (10, -400)
                    displacementNode.inputs[0].default_value = 0.1
                    displacementNode.inputs[1].default_value = 0
                    # Add converter>RGB Separator node
                    RGBSplitterNode = nodes.new("ShaderNodeSeparateRGB")
                    RGBSplitterNode.location = (-250, -499)
                    # Import normal map and normal map node setup.
                    displacementPath = displacementPath[0].replace("\\", "/")
                    displacementMapNode = nodes.new('ShaderNodeTexImage')
                    displacementMapNode.location = (-640, -740)
                    displacementMapNode.image = bpy.data.images.load(displacementPath)
                    displacementMapNode.show_texture = True
                    displacementMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add displacementMapNode to RGBSplitterNode connection
                    mat.node_tree.links.new(RGBSplitterNode.inputs[0], displacementMapNode.outputs[0])
                    # Add RGBSplitterNode to displacementNode connection
                    mat.node_tree.links.new(displacementNode.inputs[2], RGBSplitterNode.outputs[0])
                    # Add normalNode connection to the material output displacement node
                    mat.node_tree.links.new(nodes.get(materialOutputName).inputs[2], displacementNode.outputs[0])
                    mat.cycles.displacement_method = 'BOTH'
                    # Add mapping node connection in order to support tiling
                    if self.isCycles:
                        mat.node_tree.links.new(displacementMapNode.inputs[0], mappingNode.outputs[0])

            if self.DisplacementSetup == "regular":
                pass
        return
    
    def SetupMaterial3DAsset (self, mat):
        print("Setting up material for 3D Asset.")
        
        nodes = mat.node_tree.nodes
        # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
        maps_ = [item[1] for item in self.textureList]
        parentName = "Principled BSDF"
        materialOutputName = "Material Output"

        colorSpaces = getColorspaces()

        mat.node_tree.nodes[parentName].distribution = 'MULTI_GGX'
        mat.node_tree.nodes[parentName].inputs[4].default_value = 1 if self.isMetal else 0 # Metallic value
        mat.node_tree.nodes[parentName].inputs[14].default_value = self.IOR

        use_diffuse = True
        # Create the albedo x ao setup.
        if "albedo" in maps_:
            if "ao" in maps_:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                aoPath = [item[2] for item in self.textureList if item[1] == "ao"]
                if len(albedoPath) >= 1 and  len(aoPath) >= 1:
                    use_diffuse = False
                    #Add Color>MixRGB node, transform it in the node editor, change it's operation to Multiply and finally we colapse the node.
                    multiplyNode = nodes.new("ShaderNodeMixRGB")
                    multiplyNode.blend_type = 'MULTIPLY'
                    multiplyNode.location = (-250, 320)
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 460)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    #Import ao and ao node setup.
                    aoPath = aoPath[0].replace("\\", "/")
                    aoNode = nodes.new('ShaderNodeTexImage')
                    aoNode.location = (-640, 200)
                    aoNode.image = bpy.data.images.load(aoPath)
                    aoNode.show_texture = True
                    aoNode.image.colorspace_settings.name = colorSpaces[1]
                    # Conned albedo and ao node to the multiply node.
                    mat.node_tree.links.new(multiplyNode.inputs[1], albedoNode.outputs[0])
                    mat.node_tree.links.new(multiplyNode.inputs[2], aoNode.outputs[0])
                    # Connect multiply node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], multiplyNode.outputs[0])
            else:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                if len(albedoPath) >= 1:
                    use_diffuse = False
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 420)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    # Connect albedo node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], albedoNode.outputs[0])

        # Create the diffuse setup.
        if "diffuse" in maps_ and use_diffuse:
            diffusePath = [item[2] for item in self.textureList if item[1] == "diffuse"]
            if len(diffusePath) >= 1:
                # Import diffuse and diffuse node setup.
                diffusePath = diffusePath[0].replace("\\", "/")
                diffuseNode = nodes.new('ShaderNodeTexImage')
                diffuseNode.location = (-640, 420)
                diffuseNode.image = bpy.data.images.load(diffusePath)
                diffuseNode.show_texture = True
                diffuseNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect diffuse node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[0], diffuseNode.outputs[0])
        
        use_metalness = True
        # Create the specular setup.
        if "specular" in maps_:
            specularPath = [item[2] for item in self.textureList if item[1] == "specular"]
            if len(specularPath) >= 1:
                use_metalness = False
                # Import specular and specular node setup.
                specularPath = specularPath[0].replace("\\", "/")
                specularNode = nodes.new('ShaderNodeTexImage')
                specularNode.location = (-1150, 200)
                specularNode.image = bpy.data.images.load(specularPath)
                specularNode.show_texture = True
                specularNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[5], specularNode.outputs[0])

        # Create the metalness setup. Use metalness if specular is missing
        if "metalness" in maps_ and use_metalness:
            metalnessPath = [item[2] for item in self.textureList if item[1] == "metalness"]
            if len(metalnessPath) >= 1:
                # Import specular and specular node setup.
                metalnessPath = metalnessPath[0].replace("\\", "/")
                metalnessNode = nodes.new('ShaderNodeTexImage')
                metalnessNode.location = (-1150, 200)
                metalnessNode.image = bpy.data.images.load(metalnessPath)
                metalnessNode.show_texture = True
                metalnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[4], metalnessNode.outputs[0])

        use_gloss = True
        # Create the roughness setup.
        if "roughness" in maps_:
            roughnessPath = [item[2] for item in self.textureList if item[1] == "roughness"]
            if len(roughnessPath) >= 1:
                use_gloss = False
                # Import roughness and roughness node setup.
                roughnessPath = roughnessPath[0].replace("\\", "/")
                roughnessNode = nodes.new('ShaderNodeTexImage')
                roughnessNode.location = (-1150, -60)
                roughnessNode.image = bpy.data.images.load(roughnessPath)
                roughnessNode.show_texture = True
                roughnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], roughnessNode.outputs[0])
        
        # Create the gloss setup.
        if "gloss" in maps_ and use_gloss:
            glossPath = [item[2] for item in self.textureList if item[1] == "gloss"]
            if len(glossPath) >= 1:
                # Add vector>bump node
                invertNode = nodes.new("ShaderNodeInvert")
                invertNode.location = (-250, 68)
                # Import roughness and roughness node setup.
                glossPath = glossPath[0].replace("\\", "/")
                glossNode = nodes.new('ShaderNodeTexImage')
                glossNode.location = (-1150, -60)
                glossNode.image = bpy.data.images.load(glossPath)
                glossNode.show_texture = True
                glossNode.image.colorspace_settings.name = colorSpaces[1]
                # Add glossNode to invertNode connection
                mat.node_tree.links.new(invertNode.inputs[1], glossNode.outputs[0])
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], invertNode.outputs[0])

        # If HIGH POLY selected > use normal_bump and no displacement
        # If LODs selected > use corresponding LODs normal + displacement
        if self.isHighPoly:
            # Create the normal setup if the LiveLink did not setup normal + bump.
            if "normal" in maps_:
                normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
                if len(normalPath) >= 1:
                    setup_normal = False
                    # Add vector>normal map node
                    normalNode = nodes.new("ShaderNodeNormalMap")
                    normalNode.location = (-250, -170)
                    # Import normal map and normal map node setup.
                    normalPath = normalPath[0].replace("\\", "/")
                    normalMapNode = nodes.new('ShaderNodeTexImage')
                    normalMapNode.location = (-640, -207)
                    normalMapNode.image = bpy.data.images.load(normalPath)
                    normalMapNode.show_texture = True
                    normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add normalMapNode to normalNode connection
                    mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                    # Add normalNode connection to the material parent node
                    mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])
        else:
            setup_normal = True
            # Create the normal + bump setup.
            if "normal" in maps_ and "bump" in maps_:
                normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
                bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
                if len(normalPath) >= 1 and  len(bumpPath) >= 1:
                    setup_normal = False
                    # Add vector>bump node
                    bumpNode = nodes.new("ShaderNodeBump")
                    bumpNode.location = (-250, -170)
                    bumpNode.inputs[0].default_value = 0.1
                    # Import bump map and bump map node setup.
                    bumpPath = bumpPath[0].replace("\\", "/")
                    bumpMapNode = nodes.new('ShaderNodeTexImage')
                    bumpMapNode.location = (-640, -130)
                    bumpMapNode.image = bpy.data.images.load(bumpPath)
                    bumpMapNode.show_texture = True
                    bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add vector>normal map node
                    normalNode = nodes.new("ShaderNodeNormalMap")
                    normalNode.location = (-640, -400)
                    # Import normal map and normal map node setup.
                    normalPath = normalPath[0].replace("\\", "/")
                    normalMapNode = nodes.new('ShaderNodeTexImage')
                    normalMapNode.location = (-1150, -580)
                    normalMapNode.image = bpy.data.images.load(normalPath)
                    normalMapNode.show_texture = True
                    normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add normalMapNode to normalNode connection
                    mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                    # Add bumpMapNode and normalNode connection to the bumpNode
                    mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                    mat.node_tree.links.new(bumpNode.inputs[3], normalNode.outputs[0])
                    # Add bumpNode connection to the material parent node
                    mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])

            # Create the normal setup if the LiveLink did not setup normal + bump.
            if "normal" in maps_ and setup_normal:
                normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
                if len(normalPath) >= 1:
                    setup_normal = False
                    # Add vector>normal map node
                    normalNode = nodes.new("ShaderNodeNormalMap")
                    normalNode.location = (-250, -170)
                    # Import normal map and normal map node setup.
                    normalPath = normalPath[0].replace("\\", "/")
                    normalMapNode = nodes.new('ShaderNodeTexImage')
                    normalMapNode.location = (-640, -207)
                    normalMapNode.image = bpy.data.images.load(normalPath)
                    normalMapNode.show_texture = True
                    normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add normalMapNode to normalNode connection
                    mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                    # Add normalNode connection to the material parent node
                    mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])

            # Create the normal setup if the LiveLink did not setup normal + bump.
            if "bump" in maps_ and setup_normal:
                bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
                if len(bumpPath) >= 1:
                    setup_normal = False
                    # Add vector>bump node
                    bumpNode = nodes.new("ShaderNodeBump")
                    bumpNode.location = (-250, -170)
                    bumpNode.inputs[0].default_value = 0.1
                    # Import bump map and bump map node setup.
                    bumpPath = bumpPath[0].replace("\\", "/")
                    bumpMapNode = nodes.new('ShaderNodeTexImage')
                    bumpMapNode.location = (-640, -207)
                    bumpMapNode.image = bpy.data.images.load(bumpPath)
                    bumpMapNode.show_texture = True
                    bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add bumpMapNode and normalNode connection to the bumpNode
                    mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                    # Add bumpNode connection to the material parent node
                    mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
        
            # Create the displacement setup.
            if "displacement" in maps_:
                if self.DisplacementSetup == "adaptive":
                    displacementPath = [item[2] for item in self.textureList if item[1] == "displacement"]
                    if len(displacementPath) >= 1:
                        # Add vector>displacement map node
                        displacementNode = nodes.new("ShaderNodeDisplacement")
                        displacementNode.location = (10, -400)
                        displacementNode.inputs[0].default_value = 0.1
                        displacementNode.inputs[1].default_value = 0
                        # Add converter>RGB Separator node
                        RGBSplitterNode = nodes.new("ShaderNodeSeparateRGB")
                        RGBSplitterNode.location = (-250, -499)
                        # Import normal map and normal map node setup.
                        displacementPath = displacementPath[0].replace("\\", "/")
                        displacementMapNode = nodes.new('ShaderNodeTexImage')
                        displacementMapNode.location = (-640, -740)
                        displacementMapNode.image = bpy.data.images.load(displacementPath)
                        displacementMapNode.show_texture = True
                        displacementMapNode.image.colorspace_settings.name = colorSpaces[1]
                        # Add displacementMapNode to RGBSplitterNode connection
                        mat.node_tree.links.new(RGBSplitterNode.inputs[0], displacementMapNode.outputs[0])
                        # Add RGBSplitterNode to displacementNode connection
                        mat.node_tree.links.new(displacementNode.inputs[2], RGBSplitterNode.outputs[0])
                        # Add normalNode connection to the material output displacement node
                        mat.node_tree.links.new(nodes.get(materialOutputName).inputs[2], displacementNode.outputs[0])
                        mat.cycles.displacement_method = 'BOTH'

                if self.DisplacementSetup == "regular":
                    pass
        return
        
    def SetupMaterial3DPlant (self, mat):
        print("Setting up material for 3D Plant.")
        
        nodes = mat.node_tree.nodes
        # Get a list of all available texture maps. item[1] returns the map type (albedo, normal, etc...).
        maps_ = [item[1] for item in self.textureList]
        parentName = "Principled BSDF"
        materialOutputName = "Material Output"

        colorSpaces = getColorspaces()

        mat.node_tree.nodes[parentName].distribution = 'MULTI_GGX'
        mat.node_tree.nodes[parentName].inputs[4].default_value = 1 if self.isMetal else 0 # Metallic value
        mat.node_tree.nodes[parentName].inputs[14].default_value = self.IOR

        if (self.assetType == "3dplant" and self.isBillboard):
            mat.blend_method = 'BLEND'

        use_diffuse = True
        # Create the albedo x ao setup.
        if "albedo" in maps_:
            if "ao" in maps_:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                aoPath = [item[2] for item in self.textureList if item[1] == "ao"]
                if len(albedoPath) >= 1 and  len(aoPath) >= 1:
                    use_diffuse = False
                    #Add Color>MixRGB node, transform it in the node editor, change it's operation to Multiply and finally we colapse the node.
                    multiplyNode = nodes.new("ShaderNodeMixRGB")
                    multiplyNode.blend_type = 'MULTIPLY'
                    multiplyNode.location = (-250, 320)
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 460)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    #Import ao and ao node setup.
                    aoPath = aoPath[0].replace("\\", "/")
                    aoNode = nodes.new('ShaderNodeTexImage')
                    aoNode.location = (-640, 200)
                    aoNode.image = bpy.data.images.load(aoPath)
                    aoNode.show_texture = True
                    aoNode.image.colorspace_settings.name = colorSpaces[1]
                    # Conned albedo and ao node to the multiply node.
                    mat.node_tree.links.new(multiplyNode.inputs[1], albedoNode.outputs[0])
                    mat.node_tree.links.new(multiplyNode.inputs[2], aoNode.outputs[0])
                    # Connect multiply node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], multiplyNode.outputs[0])
            else:
                albedoPath = [item[2] for item in self.textureList if item[1] == "albedo"]
                if len(albedoPath) >= 1:
                    use_diffuse = False
                    #Import albedo and albedo node setup.
                    albedoPath = albedoPath[0].replace("\\", "/")
                    albedoNode = nodes.new('ShaderNodeTexImage')
                    albedoNode.location = (-640, 420)
                    albedoNode.image = bpy.data.images.load(albedoPath)
                    albedoNode.show_texture = True
                    albedoNode.image.colorspace_settings.name = colorSpaces[0]
                    # Connect albedo node to the material parent node.
                    mat.node_tree.links.new(nodes.get(parentName).inputs[0], albedoNode.outputs[0])

        # Create the diffuse setup.
        if "diffuse" in maps_ and use_diffuse:
            diffusePath = [item[2] for item in self.textureList if item[1] == "diffuse"]
            if len(diffusePath) >= 1:
                # Import diffuse and diffuse node setup.
                diffusePath = diffusePath[0].replace("\\", "/")
                diffuseNode = nodes.new('ShaderNodeTexImage')
                diffuseNode.location = (-640, 420)
                diffuseNode.image = bpy.data.images.load(diffusePath)
                diffuseNode.show_texture = True
                diffuseNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect diffuse node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[0], diffuseNode.outputs[0])
        
        use_metalness = True
        # Create the specular setup.
        if "specular" in maps_:
            specularPath = [item[2] for item in self.textureList if item[1] == "specular"]
            if len(specularPath) >= 1:
                use_metalness = False
                # Import specular and specular node setup.
                specularPath = specularPath[0].replace("\\", "/")
                specularNode = nodes.new('ShaderNodeTexImage')
                specularNode.location = (-1150, 200)
                specularNode.image = bpy.data.images.load(specularPath)
                specularNode.show_texture = True
                specularNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[5], specularNode.outputs[0])

        # Create the metalness setup. Use metalness if specular is missing
        if "metalness" in maps_ and use_metalness:
            metalnessPath = [item[2] for item in self.textureList if item[1] == "metalness"]
            if len(metalnessPath) >= 1:
                # Import specular and specular node setup.
                metalnessPath = metalnessPath[0].replace("\\", "/")
                metalnessNode = nodes.new('ShaderNodeTexImage')
                metalnessNode.location = (-1150, 200)
                metalnessNode.image = bpy.data.images.load(metalnessPath)
                metalnessNode.show_texture = True
                metalnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect specular node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[4], metalnessNode.outputs[0])

        use_gloss = True
        # Create the roughness setup.
        if "roughness" in maps_:
            roughnessPath = [item[2] for item in self.textureList if item[1] == "roughness"]
            if len(roughnessPath) >= 1:
                use_gloss = False
                # Import roughness and roughness node setup.
                roughnessPath = roughnessPath[0].replace("\\", "/")
                roughnessNode = nodes.new('ShaderNodeTexImage')
                roughnessNode.location = (-1150, -60)
                roughnessNode.image = bpy.data.images.load(roughnessPath)
                roughnessNode.show_texture = True
                roughnessNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], roughnessNode.outputs[0])
        
        # Create the gloss setup.
        if "gloss" in maps_ and use_gloss:
            glossPath = [item[2] for item in self.textureList if item[1] == "gloss"]
            if len(glossPath) >= 1:
                # Add vector>bump node
                invertNode = nodes.new("ShaderNodeInvert")
                invertNode.location = (-250, 68)
                # Import roughness and roughness node setup.
                glossPath = glossPath[0].replace("\\", "/")
                glossNode = nodes.new('ShaderNodeTexImage')
                glossNode.location = (-1150, -60)
                glossNode.image = bpy.data.images.load(glossPath)
                glossNode.show_texture = True
                glossNode.image.colorspace_settings.name = colorSpaces[1]
                # Add glossNode to invertNode connection
                mat.node_tree.links.new(invertNode.inputs[1], glossNode.outputs[0])
                # Connect roughness node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[7], invertNode.outputs[0])

        # Create the opacity setup.
        if "opacity" in maps_:
            opacityPath = [item[2] for item in self.textureList if item[1] == "opacity"]
            if len(opacityPath) >= 1:
                # Import opacity and opacity node setup.
                opacityPath = opacityPath[0].replace("\\", "/")
                opacityNode = nodes.new('ShaderNodeTexImage')
                opacityNode.location = (-1550, -160)
                opacityNode.image = bpy.data.images.load(opacityPath)
                opacityNode.show_texture = True
                opacityNode.image.colorspace_settings.name = colorSpaces[1]
                # Connect opacity node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[18], opacityNode.outputs[0])

        # Create the translucency setup.
        if "translucency" in maps_:
            translucencyPath = [item[2] for item in self.textureList if item[1] == "translucency"]
            if len(translucencyPath) >= 1:
                # Import translucency and translucency node setup.
                translucencyPath = translucencyPath[0].replace("\\", "/")
                translucencyNode = nodes.new('ShaderNodeTexImage')
                translucencyNode.location = (-1550, -420)
                translucencyNode.image = bpy.data.images.load(translucencyPath)
                translucencyNode.show_texture = True
                translucencyNode.image.colorspace_settings.name = colorSpaces[0]
                # Connect translucency node to the material parent node.
                mat.node_tree.links.new(nodes.get(parentName).inputs[15], translucencyNode.outputs[0])

        setup_normal = True
        # Create the normal + bump setup.
        if "normal" in maps_ and "bump" in maps_:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(normalPath) >= 1 and  len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -130)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-640, -400)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-1150, -580)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                mat.node_tree.links.new(bumpNode.inputs[3], normalNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "normal" in maps_ and setup_normal:
            normalPath = [item[2] for item in self.textureList if item[1] == "normal"]
            if len(normalPath) >= 1:
                setup_normal = False
                # Add vector>normal map node
                normalNode = nodes.new("ShaderNodeNormalMap")
                normalNode.location = (-250, -170)
                # Import normal map and normal map node setup.
                normalPath = normalPath[0].replace("\\", "/")
                normalMapNode = nodes.new('ShaderNodeTexImage')
                normalMapNode.location = (-640, -207)
                normalMapNode.image = bpy.data.images.load(normalPath)
                normalMapNode.show_texture = True
                normalMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add normalMapNode to normalNode connection
                mat.node_tree.links.new(normalNode.inputs[1], normalMapNode.outputs[0])
                # Add normalNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], normalNode.outputs[0])

        # Create the normal setup if the LiveLink did not setup normal + bump.
        if "bump" in maps_ and setup_normal:
            bumpPath = [item[2] for item in self.textureList if item[1] == "bump"]
            if len(bumpPath) >= 1:
                setup_normal = False
                # Add vector>bump node
                bumpNode = nodes.new("ShaderNodeBump")
                bumpNode.location = (-250, -170)
                bumpNode.inputs[0].default_value = 0.1
                # Import bump map and bump map node setup.
                bumpPath = bumpPath[0].replace("\\", "/")
                bumpMapNode = nodes.new('ShaderNodeTexImage')
                bumpMapNode.location = (-640, -207)
                bumpMapNode.image = bpy.data.images.load(bumpPath)
                bumpMapNode.show_texture = True
                bumpMapNode.image.colorspace_settings.name = colorSpaces[1]
                # Add bumpMapNode and normalNode connection to the bumpNode
                mat.node_tree.links.new(bumpNode.inputs[2], bumpMapNode.outputs[0])
                # Add bumpNode connection to the material parent node
                mat.node_tree.links.new(nodes.get(parentName).inputs[19], bumpNode.outputs[0])
    
        # Create the displacement setup.
        if "displacement" in maps_:
            if self.DisplacementSetup == "adaptive":
                displacementPath = [item[2] for item in self.textureList if item[1] == "displacement"]
                if len(displacementPath) >= 1:
                    # Add vector>displacement map node
                    displacementNode = nodes.new("ShaderNodeDisplacement")
                    displacementNode.location = (10, -400)
                    displacementNode.inputs[0].default_value = 0.1
                    displacementNode.inputs[1].default_value = 0
                    # Add converter>RGB Separator node
                    RGBSplitterNode = nodes.new("ShaderNodeSeparateRGB")
                    RGBSplitterNode.location = (-250, -499)
                    # Import normal map and normal map node setup.
                    displacementPath = displacementPath[0].replace("\\", "/")
                    displacementMapNode = nodes.new('ShaderNodeTexImage')
                    displacementMapNode.location = (-640, -740)
                    displacementMapNode.image = bpy.data.images.load(displacementPath)
                    displacementMapNode.show_texture = True
                    displacementMapNode.image.colorspace_settings.name = colorSpaces[1]
                    # Add displacementMapNode to RGBSplitterNode connection
                    mat.node_tree.links.new(RGBSplitterNode.inputs[0], displacementMapNode.outputs[0])
                    # Add RGBSplitterNode to displacementNode connection
                    mat.node_tree.links.new(displacementNode.inputs[2], RGBSplitterNode.outputs[0])
                    # Add normalNode connection to the material output displacement node
                    mat.node_tree.links.new(nodes.get(materialOutputName).inputs[2], displacementNode.outputs[0])
                    mat.cycles.displacement_method = 'BOTH'

            if self.DisplacementSetup == "regular":
                pass
        return

class ms_Init(threading.Thread):
    
	#Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self, importer):
        threading.Thread.__init__(self)
        self.importer = importer

	#Start the thread to start listing to the port.
    def run(self):
        try:
            run_livelink = True
            host, port = 'localhost', 28888
            #Making a socket object.
            socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #Binding the socket to host and port number mentioned at the start.
            socket_.bind((host, port))

            #Run until the thread starts receiving data.
            while run_livelink:
                socket_.listen(5)
                #Accept connection request.
                client, addr = socket_.accept()
                data = ""
                buffer_size = 4096*2
                #Receive data from the client. 
                data = client.recv(buffer_size)
                if data == b'Bye Megascans':
                    run_livelink = False
                    break

                #If any data is received over the port.
                if data != "":
                    self.TotalData = b""
                    self.TotalData += data #Append the previously received data to the Total Data.
                    #Keep running until the connection is open and we are receiving data.
                    while run_livelink:
                        #Keep receiving data from client.
                        data = client.recv(4096*2)
                        if data == b'Bye Megascans':
                            run_livelink = False
                            break
                        #if we are getting data keep appending it to the Total data.
                        if data : self.TotalData += data
                        else:
                            #Once the data transmission is over call the importer method and send the collected TotalData.
                            self.importer(self.TotalData)
                            break
        except Exception as e:
            print( "Megascans LiveLink Error initializing the thread. Error: ", str(e) )

class thread_checker(threading.Thread):
    
	#Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self):
        threading.Thread.__init__(self)

	#Start the thread to start listing to the port.
    def run(self):
        try:
            run_checker = True
            while run_checker:
                time.sleep(3)
                for i in threading.enumerate():
                    if(i.getName() == "MainThread" and i.is_alive() == False):
                        host, port = 'localhost', 28888
                        s = socket.socket()
                        s.connect((host,port))
                        data = "Bye Megascans"
                        s.send(data.encode())
                        s.close()
                        run_checker = False
                        break
        except Exception as e:
            print( "Megascans LiveLink Error initializing thread checker. Error: ", str(e) )
            pass

class MS_Init_LiveLink(bpy.types.Operator):

    bl_idname = "ms_livelink.py"
    bl_label = "Megascans LiveLink"
    socketCount = 0

    def execute(self, context):

        try:
            globals()['Megascans_DataSet'] = None
            self.thread_ = threading.Thread(target = self.socketMonitor)
            self.thread_.start()
            bpy.app.timers.register(self.newDataMonitor)
            return {'FINISHED'}
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin. Error: ", str(e) )
            return {"FAILED"}

    def newDataMonitor(self):
        try:
            if globals()['Megascans_DataSet'] != None:
                MS_Init_ImportProcess()
                globals()['Megascans_DataSet'] = None       
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (newDataMonitor). Error: ", str(e) )
            return {"FAILED"}
        return 1.0


    def socketMonitor(self):
        try:
            #Making a thread object
            threadedServer = ms_Init(self.importer)
            #Start the newly created thread.
            threadedServer.start()
            #Making a thread object
            thread_checker_ = thread_checker()
            #Start the newly created thread.
            thread_checker_.start()
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (socketMonitor). Error: ", str(e) )
            return {"FAILED"}

    def importer (self, recv_data):
        try:
            globals()['Megascans_DataSet'] = recv_data
        except Exception as e:
            print( "Megascans LiveLink error starting blender plugin (importer). Error: ", str(e) )
            return {"FAILED"}
        
def show_error_dialog(self, context, message = "Test message."):
     self.report({'INFO'}, message)

def menu_func_import(self, context):
    self.layout.operator(MS_Init_LiveLink.bl_idname, text="Megascans LiveLink")

def getColorspaces():
    if os.environ.get("OCIO"):
        return ["Utility - sRGB - Texture", "Utility - Raw"]
    else:
        return ["sRGB", "Non-Color"]

def register():
    bpy.utils.register_class(MS_Init_LiveLink)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    # bpy.utils.unregister_class(MS_Init_LiveLink)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
