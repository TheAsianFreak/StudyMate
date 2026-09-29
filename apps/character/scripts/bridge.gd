extends Node
## JavaScriptBridge transport between Godot and the renderer Director.
##
## All JS interop lives here. Messages are JSON strings in the format of
## packages/protocol/schema/godot.schema.json. The Director must define
## `window.studymateHost = { attachGodot(cb), receive(json) }` before the engine starts.
## Coordinates crossing this boundary are window CSS pixels.

signal command_received(msg: Dictionary)

const HOST_NAME := "studymateHost"
const MAX_RECORDED := 4096
## Emscripten renders Godot's frame into an offscreen back buffer and, when it
## blits that to the canvas every frame, reads gl.getParameter(SCISSOR_TEST).
## Chrome answers that query with a synchronous round trip that waits until the
## GPU process has executed everything queued, so every frame took CPU time plus
## the full GPU-process time (100+ ms frames under GPU load). This shim tracks
## the scissor-test state on the JS side, so the query never leaves the page.
## Set window.studymateNoGlShim = true before the engine starts to disable it.
const SCISSOR_SHIM := """(() => {
	const proto = window.WebGL2RenderingContext && WebGL2RenderingContext.prototype;
	if (!proto || proto.__studymateScissorShim || window.studymateNoGlShim) return false;
	proto.__studymateScissorShim = true;
	const SCISSOR_TEST = 0x0C11;
	const state = new WeakMap();
	const enable = proto.enable, disable = proto.disable, getParameter = proto.getParameter, isEnabled = proto.isEnabled;
	proto.enable = function (cap) { if (cap === SCISSOR_TEST) state.set(this, true); return enable.call(this, cap); };
	proto.disable = function (cap) { if (cap === SCISSOR_TEST) state.set(this, false); return disable.call(this, cap); };
	proto.getParameter = function (pname) {
		if (pname !== SCISSOR_TEST) return getParameter.call(this, pname);
		let on = state.get(this);
		if (on === undefined) { on = getParameter.call(this, pname); state.set(this, on); }
		return on;
	};
	proto.isEnabled = function (cap) { return cap === SCISSOR_TEST ? this.getParameter(cap) : isEnabled.call(this, cap); };
	return true;
})()"""

## Test hook: off the web (headless tests, desktop runs) outgoing messages are
## kept in `sent` instead of reaching a Director; tests feed commands via inject().
var record_sent := false
var sent: Array[Dictionary] = []

var _host: JavaScriptObject
var _window: JavaScriptObject
## Must stay referenced for the callback to remain valid on the JS side.
var _receive_cb: JavaScriptObject
var _viewport_per_css := 1.0


func _ready() -> void:
	# Connected before any scene node so the scale is fresh when others react to resizes.
	get_viewport().size_changed.connect(_update_scale)
	FrameProfiler.enabled = _profiling_requested()
	if not OS.has_feature("web"):
		record_sent = true
		push_warning("Bridge: not running on web, JS bridge disabled (recording messages)")
		return
	_window = JavaScriptBridge.get_interface("window")
	# The StudyMate shell installs the same shim itself (its CSP forbids eval);
	# only standalone web pages need it installed from here.
	if _window == null or not _window.get("studymateGlShimInstalled"):
		JavaScriptBridge.eval(SCISSOR_SHIM, true)
	_update_scale()
	_host = JavaScriptBridge.get_interface(HOST_NAME)
	if _host == null:
		push_error("Bridge: window.%s is not defined" % HOST_NAME)
		return
	_receive_cb = JavaScriptBridge.create_callback(_on_js_message)
	_host.call("attachGodot", _receive_cb)


## window.studymateProfile = true | "flag,flag" (web) or the user argument
## --profile[=flag,flag] (native). Flags go to FrameProfiler.flags.
func _profiling_requested() -> bool:
	var value: Variant = null
	if OS.has_feature("web"):
		var window := JavaScriptBridge.get_interface("window")
		value = window.get("studymateProfile") if window != null else null
	else:
		for arg: String in OS.get_cmdline_user_args():
			if arg == "--profile":
				value = true
			elif arg.begins_with("--profile="):
				value = arg.trim_prefix("--profile=")
	if value is String:
		FrameProfiler.flags = (value as String).split(",", false)
		return true
	return value == true


func is_connected_to_host() -> bool:
	return _host != null


func send(msg: Dictionary) -> void:
	if record_sent:
		if sent.size() >= MAX_RECORDED:
			sent.pop_front()
		sent.append(msg.duplicate(true))
	if _host == null:
		return
	_host.call("receive", JSON.stringify(msg))


## Test hook: delivers a command as if the Director had sent it (JSON round
## trip, so numbers arrive as floats exactly like on the web).
func inject(msg: Dictionary) -> void:
	_on_js_message([JSON.stringify(msg)])


## Tells the page which frame rate to allow (it caps requestAnimationFrame).
func set_frame_rate(fps: int) -> void:
	if _window != null:
		_window.set("studymateFrameRate", fps)


## Viewport pixels per CSS pixel (devicePixelRatio as seen by the canvas).
func viewport_per_css() -> float:
	return _viewport_per_css


func _update_scale() -> void:
	if _window == null:
		return
	var css_width: float = float(_window.get("innerWidth"))
	if css_width > 0.0:
		_viewport_per_css = get_viewport().get_visible_rect().size.x / css_width


func css_to_viewport(p: Vector2) -> Vector2:
	return p * viewport_per_css()


func viewport_to_css(p: Vector2) -> Vector2:
	return p / viewport_per_css()


func _on_js_message(args: Array) -> void:
	if args.is_empty() or typeof(args[0]) != TYPE_STRING:
		push_warning("Bridge: expected a JSON string")
		return
	var parsed: Variant = JSON.parse_string(args[0])
	if typeof(parsed) != TYPE_DICTIONARY or not (parsed as Dictionary).has("type"):
		push_warning("Bridge: malformed message %s" % args[0])
		return
	command_received.emit(parsed as Dictionary)
