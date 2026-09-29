class_name AvatarState
extends RefCounted
## Command state shared by Character and its AvatarBody. Character writes it from
## Director commands; the body reads it every frame and animates toward it, so a
## body swap keeps the current gesture, gaze and expression. Positions are world
## space on or near the z = 0 character plane.

enum Look { FORWARD, USER, POINT }
enum Hand { RIGHT, LEFT }

## Gestures that move a hand (and therefore report hand_pos).
const HAND_GESTURES: Array[String] = ["write", "point", "tap_desk", "throw"]
## Fraction of a throw gesture at which the chalk leaves the hand.
const THROW_RELEASE := 0.46
const VISEMES: Array[String] = ["aa", "ih", "ou", "ee", "oh"]

## Active gesture name; empty when none. "idle" is a gesture that holds the rest pose.
var gesture := ""
var gesture_time := 0.0
var gesture_duration := 0.0
var gesture_hand := Hand.RIGHT

## Latest ik_target (writing head). has_ik_target stays true once set.
var ik_target := Vector3.ZERO
var has_ik_target := false
## Smoothed velocity of the ik_target (world units/s): stroke direction and speed.
var ik_velocity := Vector3.ZERO

## Effective gaze for this frame (Character resolves commands vs gesture gaze).
var look := Look.FORWARD
var look_point := Vector3.ZERO
## Where a point gesture aims (resolved by Character at gesture start / on updates).
var point_target := Vector3.ZERO

var emotion := "neutral"
var emotion_weight := 0.0

var visemes: Dictionary = {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
## Seconds since the last viseme command.
var viseme_age := INF

## True while the gesturing hand holds a chalk (write, throw before release).
var holding_chalk := false

## Locomotion, written by Character every frame.
## World velocity of the feet point (units/s, x/y screen plane).
var velocity := Vector3.ZERO
## True while a move_to is in progress (including its ease-out).
var moving := false
## 0 = walk, 1 = side-step shuffle (short moves), blended.
var shuffle := 0.0
## Rig yaw rate (rad/s) while turning.
var turn_speed := 0.0
## Set when the character jumped (set_pos, body swap): bodies re-plant their feet.
var teleported := true

## Picked up by the collar (grab/release), written by Character every frame.
## 0..1 blend of the dangling pose: 1 while held or falling, 0 once landed.
var hang := 0.0
var grabbed := false
## Falling after a release, until the feet touch down.
var airborne := false
## Pendulum angle of the hanging body (rad, + = feet swing toward screen +x) and its rate.
var swing := 0.0
var swing_velocity := 0.0
## World velocity of the grab point while held (units/s).
var grab_velocity := Vector3.ZERO
## 0..1 flailing intensity while held (a burst on pick-up, more when dragged fast).
var fluster := 0.0
## Seconds since the feet touched down after a release; -1 when not landing.
var land_time := -1.0
## Downward speed at touchdown (units/s).
var land_speed := 0.0
## Set on the touchdown frame only: bodies plant the feet where they are.
var touchdown := false


func gesture_phase() -> float:
	if gesture_duration <= 0.0:
		return 1.0
	return clampf(gesture_time / gesture_duration, 0.0, 1.0)


func is_hand_gesture() -> bool:
	return HAND_GESTURES.has(gesture)


## A gesture that needs the gaze on its target (no idle glances meanwhile).
func is_focused() -> bool:
	return gesture != "" and gesture != "idle"


## True while the Director talks through the character (visemes streaming).
func is_talking() -> bool:
	return viseme_age < 0.5
