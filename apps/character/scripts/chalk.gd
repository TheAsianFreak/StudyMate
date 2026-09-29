class_name ChalkThrow
extends Node3D
## A thrown chalk. The scene camera is orthographic, so flying "toward the
## viewer" is faked: the chalk follows a ballistic arc in a virtual space whose
## depth axis runs toward a virtual eye in front of the screen centre, and is
## drawn at its perspective projection (position and scale) in the scene. When
## it reaches the glass it reports the impact point and bursts into chalk dust.
## The node frees itself once the dust has settled.

signal impacted(point: Vector3)

## Per strength: flight time (s), chalk size factor, magnification at impact,
## dust/chip particle counts and burst speed factor.
const PROFILES := {
	"soft": {"time": 0.7, "size": 0.85, "magnify": 3.5, "dust": 14, "chips": 3, "burst": 0.8},
	"normal": {"time": 0.52, "size": 1.0, "magnify": 4.5, "dust": 24, "chips": 5, "burst": 1.0},
	"hard": {"time": 0.36, "size": 1.2, "magnify": 5.5, "dust": 40, "chips": 8, "burst": 1.35},
}
## Virtual eye distance from the character plane, world units.
const EYE_DISTANCE := 6.0
const GRAVITY := 6.0
## Draw depth range (camera sits at z = 10), keeps the chalk in front of the character.
const DRAW_Z_START := 1.0
const DRAW_Z_END := 8.0
const CHALK_LENGTH := 0.075
const CHALK_RADIUS := 0.011
const CHALK_COLOR := Color(0.98, 0.97, 0.93)
const OUTLINE_COLOR := Color(0.24, 0.16, 0.28)
const CLEANUP_AFTER := 1.6

var _profile: Dictionary = PROFILES["normal"]
var _start := Vector3.ZERO  # virtual space: x, y = world, z = toward the eye
var _velocity := Vector3.ZERO
var _center := Vector2.ZERO
var _aim := Vector2.ZERO
var _time := 0.0
var _flight := 0.5
var _flying := false
var _spin_axis := Vector3.RIGHT
var _spin_speed := 0.0
var _body: Node3D  # position + perspective scale
var _spin: Node3D  # tumbling chalk mesh


## origin: world position of the hand; aim / center: world x, y of the impact
## point and of the screen centre (where the virtual eye sits).
func launch(origin: Vector3, aim: Vector2, center: Vector2, strength: String) -> void:
	_profile = PROFILES.get(strength, PROFILES["normal"])
	_center = center
	_aim = aim
	_flight = _profile.time
	var magnify: float = _profile.magnify
	var z_hit := EYE_DISTANCE * (1.0 - 1.0 / magnify)
	# Where the chalk must be at z_hit so that its projection lands on aim.
	var hit := center + (aim - center) / magnify
	_start = Vector3(origin.x, origin.y, 0.0)
	var gravity := Vector3(0.0, -GRAVITY, 0.0)
	_velocity = (Vector3(hit.x, hit.y, z_hit) - _start - 0.5 * gravity * _flight * _flight) / _flight

	_body = Node3D.new()
	add_child(_body)
	_spin = make_chalk(_profile.size)
	_body.add_child(_spin)
	_spin_axis = Vector3(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0), randf_range(-0.3, 0.3))
	if _spin_axis.length() < 0.1:
		_spin_axis = Vector3.RIGHT
	_spin_axis = _spin_axis.normalized()
	_spin_speed = randf_range(14.0, 22.0) * float(_profile.burst)
	_flying = true
	_place(0.0)


func is_flying() -> bool:
	return _flying


## Draws every chalk material once at `hidden_at` (a point behind the opaque
## body) and frees itself, so the first write/throw doesn't stall on shader
## compilation (~100 ms on WebGL).
func prewarm(hidden_at: Vector3) -> void:
	_body = Node3D.new()
	_body.position = hidden_at
	add_child(_body)
	_spin = make_chalk(0.5)
	_body.add_child(_spin)
	_burst(hidden_at, true)
	_flight = 0.3 - CLEANUP_AFTER  # cleanup 0.3 s from now


func _process(delta: float) -> void:
	_time += delta
	if _flying:
		_place(minf(_time, _flight))
		_spin.rotate(_spin_axis, _spin_speed * delta)
		if _time >= _flight:
			_impact()
	elif _time > _flight + CLEANUP_AFTER:
		queue_free()


func _place(t: float) -> void:
	var p := _start + _velocity * t + 0.5 * Vector3(0.0, -GRAVITY, 0.0) * t * t
	var magnify := EYE_DISTANCE / maxf(EYE_DISTANCE - p.z, 0.01)
	var screen := _center + (Vector2(p.x, p.y) - _center) * magnify
	var z_hit := EYE_DISTANCE * (1.0 - 1.0 / float(_profile.magnify))
	_body.position = Vector3(screen.x, screen.y, lerpf(DRAW_Z_START, DRAW_Z_END, clampf(p.z / z_hit, 0.0, 1.0)))
	_body.scale = Vector3.ONE * magnify


func _impact() -> void:
	_flying = false
	_body.visible = false
	_burst(Vector3(_aim.x, _aim.y, DRAW_Z_END), false)
	impacted.emit(Vector3(_aim.x, _aim.y, 0.0))


## quiet: one motionless tiny particle per emitter (shader prewarm).
func _burst(at: Vector3, quiet: bool) -> void:
	var k: float = 0.0 if quiet else float(_profile.burst)
	var size: float = 0.1 if quiet else float(_profile.size)
	var dust := CPUParticles3D.new()
	dust.amount = 1 if quiet else int(_profile.dust)
	dust.lifetime = 0.9
	dust.lifetime_randomness = 0.3
	dust.one_shot = true
	dust.explosiveness = 0.92
	dust.mesh = _dust_mesh()
	dust.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	dust.emission_sphere_radius = 0.06 * size
	dust.direction = Vector3(0.0, 0.2, 1.0)
	dust.spread = 180.0
	dust.initial_velocity_min = 0.5 * k
	dust.initial_velocity_max = 2.0 * k
	dust.damping_min = 2.0
	dust.damping_max = 4.0
	dust.gravity = Vector3.ZERO if quiet else Vector3(0.0, -1.2, 0.0)
	dust.scale_amount_min = 0.08 * size
	dust.scale_amount_max = 0.2 * size * k
	dust.color_ramp = _fade(Color(1.0, 1.0, 1.0, 0.9))
	dust.position = at
	add_child(dust)
	dust.emitting = true

	var chips := CPUParticles3D.new()
	chips.amount = 1 if quiet else int(_profile.chips)
	chips.lifetime = 1.1
	chips.one_shot = true
	chips.explosiveness = 1.0
	var chip_mesh := BoxMesh.new()
	chip_mesh.size = Vector3.ONE * 0.03 * size
	chip_mesh.material = _chalk_material()
	chips.mesh = chip_mesh
	chips.direction = Vector3(0.0, 1.0, 0.3)
	chips.spread = 70.0
	chips.initial_velocity_min = 1.0 * k
	chips.initial_velocity_max = 2.6 * k
	chips.gravity = Vector3.ZERO if quiet else Vector3(0.0, -9.0, 0.0)
	chips.angular_velocity_min = -540.0
	chips.angular_velocity_max = 540.0
	chips.scale_amount_min = 0.6
	chips.scale_amount_max = 1.2
	chips.position = at + Vector3(0.0, 0.0, 0.1)
	add_child(chips)
	chips.emitting = true


static func _fade(color: Color) -> Gradient:
	var g := Gradient.new()
	g.set_color(0, color)
	g.set_color(1, Color(color, 0.0))
	return g


static func _dust_mesh() -> QuadMesh:
	var tex := GradientTexture2D.new()
	tex.width = 32
	tex.height = 32
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.gradient = _fade(Color.WHITE)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = tex
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	var quad := QuadMesh.new()
	quad.material = mat
	return quad


static func _chalk_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = CHALK_COLOR
	mat.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
	mat.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	var outline := StandardMaterial3D.new()
	outline.albedo_color = OUTLINE_COLOR
	outline.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	outline.cull_mode = BaseMaterial3D.CULL_FRONT
	outline.grow = true
	outline.grow_amount = 0.004
	mat.next_pass = outline
	return mat


## A chalk stick along local +Y, centred on the origin.
static func make_chalk(size: float) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = CHALK_RADIUS * size
	mesh.bottom_radius = CHALK_RADIUS * size * 1.05
	mesh.height = CHALK_LENGTH * size
	mesh.radial_segments = 10
	mesh.rings = 1
	mesh.material = _chalk_material()
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	return mi
