class_name AvatarLoader
extends RefCounted
## Runtime VRM (0.x / 1.0) loading through godot-vrm's glTF extensions.
## The editor plugin registers these only inside the editor, so we register the
## set matching the file's VRM version around each load.

const VrmExtension := preload("res://addons/vrm/vrm_extension.gd")
const VRMC_vrm := preload("res://addons/vrm/1.0/VRMC_vrm.gd")
const VRMC_node_constraint := preload("res://addons/vrm/1.0/VRMC_node_constraint.gd")
const VRMC_springBone := preload("res://addons/vrm/1.0/VRMC_springBone.gd")
const VRMC_materials_mtoon := preload("res://addons/vrm/1.0/VRMC_materials_mtoon.gd")
const VRMC_materials_hdr_emissiveMultiplier := preload("res://addons/vrm/1.0/VRMC_materials_hdr_emissiveMultiplier.gd")

## EditorSceneFormatImporter flags (the class is editor-only):
## IMPORT_GENERATE_TANGENT_ARRAYS (8) | IMPORT_USE_NAMED_SKIN_BINDS (16) |
## IMPORT_FORCE_DISABLE_MESH_COMPRESSION (64): uncompressed vertex attributes
## cut the WebGL GPU-process time of per-frame skinning by ~10% (measured with
## Tsukuyomi in Chrome/ANGLE D3D11); the memory cost is negligible.
const IMPORT_FLAGS := 8 | 16 | 64
const MAX_BYTES := 256 * 1024 * 1024
const GLB_CHUNK_JSON := 0x4E4F534A


## Returns {"scene": Node3D, "meta": Resource} or {"error": String}.
## A res:// path of a VRM imported by the editor (e.g. the bundled default)
## loads the imported scene; anything else is parsed at runtime.
static func load_vrm(path: String) -> Dictionary:
	if path.begins_with("res://") and ResourceLoader.exists(path, "PackedScene"):
		var packed := load(path) as PackedScene
		var imported: Node3D = packed.instantiate() as Node3D if packed != null else null
		if imported == null or imported.get("vrm_meta") == null:
			if imported != null:
				imported.free()
			return {"error": "VRM 씬이 아닙니다: %s" % path}
		return {"scene": imported, "meta": imported.get("vrm_meta")}
	if not FileAccess.file_exists(path):
		return {"error": "파일을 찾을 수 없습니다: %s" % path}
	var file := FileAccess.open(path, FileAccess.READ)
	if file.get_length() > MAX_BYTES:
		return {"error": "파일이 너무 큽니다 (최대 256MB)"}
	var bytes := file.get_buffer(file.get_length())
	file.close()

	var json := _glb_json(bytes)
	if json.is_empty():
		return {"error": "VRM(glTF 바이너리) 파일이 아닙니다"}
	var used: Array = json.get("extensionsUsed", [])
	var extensions: Array[GLTFDocumentExtension] = []
	if used.has("VRMC_vrm"):
		extensions = [
			VRMC_vrm.new(),
			VRMC_node_constraint.new(),
			VRMC_springBone.new(),
			VRMC_materials_hdr_emissiveMultiplier.new(),
			VRMC_materials_mtoon.new(),
		]
	elif used.has("VRM"):
		extensions = [VrmExtension.new()]
	else:
		return {"error": "VRM 정보가 없는 파일입니다 (일반 glTF는 지원하지 않음)"}

	# First priority: they must run before Godot's built-in ConvertImporterMesh
	# extension, which frees the ImporterMeshInstance3D nodes godot-vrm edits.
	# Inserted in reverse so they run in list order.
	for i in range(extensions.size() - 1, -1, -1):
		GLTFDocument.register_gltf_document_extension(extensions[i], true)
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	state.handle_binary_image_mode = GLTFState.HANDLE_BINARY_IMAGE_MODE_EMBED_AS_UNCOMPRESSED
	var err := doc.append_from_buffer(bytes, "", state, IMPORT_FLAGS)
	var scene: Node3D = null
	if err == OK:
		scene = doc.generate_scene(state) as Node3D
	for ext in extensions:
		GLTFDocument.unregister_gltf_document_extension(ext)

	if err != OK:
		return {"error": "VRM 파싱 실패 (%s)" % error_string(err)}
	if scene == null:
		return {"error": "씬 생성 실패"}
	return {"scene": scene, "meta": scene.get("vrm_meta")}


## Flattens VRM meta into the protocol's AvatarMeta shape.
static func meta_summary(meta: Resource) -> Dictionary:
	var summary := {
		"title": "", "authors": [], "version": "", "license_name": "", "license_url": "",
		"commercial_usage": "", "allow_redistribution": "", "modification": "",
		"credit_notation": "", "spec_version": "",
	}
	if meta == null:
		return summary
	for key: String in summary:
		var source_key := "commercial_usage_type" if key == "commercial_usage" else key
		var value: Variant = meta.get(source_key)
		if value == null:
			continue
		summary[key] = Array(value) if key == "authors" else str(value).strip_edges()
	return summary


## Reads the JSON chunk of a GLB container; empty on malformed input.
static func _glb_json(bytes: PackedByteArray) -> Dictionary:
	if bytes.size() < 20 or bytes.slice(0, 4).get_string_from_ascii() != "glTF":
		return {}
	var length := bytes.decode_u32(12)
	if bytes.decode_u32(16) != GLB_CHUNK_JSON or 20 + length > bytes.size():
		return {}
	var parsed: Variant = JSON.parse_string(bytes.slice(20, 20 + length).get_string_from_utf8())
	return parsed if parsed is Dictionary else {}
