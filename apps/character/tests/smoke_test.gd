extends SceneTree
## Headless smoke test: boots the main scene, swaps in a VRM and checks bones/bounds.
## Usage: godot --headless --path apps/character --script res://tests/smoke_test.gd -- <file.vrm>
## The full command suite is tests/command_test.gd.


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		_fail("pass a .vrm path after --")
		return
	var main: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	await process_frame

	var result := AvatarLoader.load_vrm(args[0])
	if result.has("error"):
		_fail(result.error)
		return
	var character: Character = main.get_node("Character")
	var meta := character.use_vrm(result.scene, result.meta)
	print("meta: ", meta)
	var body: VrmBody = character.body()
	print("mapped bones: ", body.get("_bones").keys())
	print("expressions: ", body.expression_names())
	print("bounds: ", character.world_bounds())
	character.move_to(Vector3(1, 0, 0), 1.0)
	for i in 10:
		await process_frame
	print("OK")
	quit(0)


func _fail(message: String) -> void:
	printerr("FAIL: ", message)
	quit(1)
