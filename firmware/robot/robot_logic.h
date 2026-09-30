#pragma once

/*
 * Control logic core.
 *
 * Deliberately free of Arduino and networking dependencies so the decision logic
 * can be compiled and tested on a workstation (see tools/firmware_logic_test.cpp).
 * Nothing in this file touches a pin, a radio or a timer object.
 */

#include <stdint.h>

#include "config.h"

namespace robotlogic {

enum class RobotState {
  Idle,
  TargetDetected,
  Approaching,
  ObstacleAvoidance,
  EmitterActive,
  Monitoring,
  Error,
};

enum class DriveCommand { Stop, Forward, TurnRight, TurnLeft, Reverse };

enum class TransitionKind {
  None,
  TargetActivityDetected,
  TargetActivityCleared,
  ObstacleDetected,
  ObstacleCleared,
  EmitterActivated,
  EmitterDeactivated,
  Fault,
};

struct Inputs {
  bool vibration_active = false;
  bool ir_active = false;
  bool vibration_configured = false;
  bool ir_configured = false;
  bool distance_valid = false;
  float distance_cm = CFG_INVALID_READING_CM;
  bool drive_ready = false;
  bool emitter_ready = false;
};

struct Outputs {
  RobotState state = RobotState::Idle;
  DriveCommand drive = DriveCommand::Stop;
  uint8_t speed_percent = 0;
  // Desired emitter command state. The caller applies it through
  // emitter::set_active() so the pin is written in exactly one place.
  bool emitter_request = false;
  // How the current activity was confirmed, for event metadata. It keeps
  // "target activity" distinguishable from "an object was close".
  TargetConfirmationMode confirmation = TARGET_CONFIRM_DISABLED;
};

struct Transition {
  TransitionKind kind = TransitionKind::None;
  RobotState from = RobotState::Idle;
  RobotState to = RobotState::Idle;
};

struct StepResult {
  Outputs outputs;
  bool has_transition = false;
  Transition transition;
  // One tick can legitimately report two things, for example the emitter arming
  // at the same moment as the obstacle ahead clearing. Silently dropping either
  // would misreport the physical sequence.
  bool has_secondary = false;
  Transition secondary;
};

struct Timings {
  uint32_t settle_ms = CFG_TARGET_SETTLE_MS;
  uint32_t avoidance_ms = CFG_AVOIDANCE_DURATION_MS;
  uint32_t avoidance_retry_ms = CFG_AVOIDANCE_RETRY_MS;
  uint32_t emitter_burst_ms = CFG_EMITTER_BURST_MS;
  uint32_t emitter_cooldown_ms = CFG_EMITTER_COOLDOWN_MS;
  uint32_t sensor_fault_ms = 3000;
  uint8_t max_bursts = CFG_EMITTER_MAX_BURSTS_PER_ACTIVITY;
  float detect_distance_cm = CFG_DETECT_DISTANCE_CM;
  float obstacle_clearance_cm = CFG_OBSTACLE_CLEARANCE_CM;
  float max_usable_distance_cm = CFG_MAX_USABLE_DISTANCE_CM;
  uint8_t motor_speed_percent = CFG_MOTOR_SPEED_PERCENT;
  uint8_t turn_speed_percent = CFG_TURN_SPEED_PERCENT;
};

class Controller {
 public:
  explicit Controller(const Timings &timings = Timings());

  // Advance the machine by one tick. Safe to call as fast as the caller likes.
  StepResult update(const Inputs &inputs, uint32_t now_ms);

  RobotState state() const { return state_; }
  bool emitter_active() const { return emitter_active_; }
  uint8_t bursts_used() const { return bursts_used_; }
  bool activity_confirmed() const { return activity_confirmed_; }

  static const char *state_name(RobotState state);
  static const char *confirmation_name(TargetConfirmationMode mode);

 private:
  bool confirm_activity(const Inputs &inputs) const;
  bool obstacle_present(const Inputs &inputs) const;
  bool in_range(const Inputs &inputs) const;
  bool distance_usable(const Inputs &inputs) const;
  bool faulted(const Inputs &inputs, uint32_t now_ms) const;
  Outputs make_outputs() const;
  StepResult emit(RobotState next, TransitionKind kind);
  StepResult emit(RobotState next, TransitionKind kind, TransitionKind secondary_kind);

  Timings timings_;
  RobotState state_ = RobotState::Idle;
  bool activity_confirmed_ = false;
  bool emitter_active_ = false;
  bool obstacle_active_ = false;
  bool faulted_ = false;
  uint8_t bursts_used_ = 0;
  TargetConfirmationMode confirmation_ = TARGET_CONFIRM_DISABLED;

  uint32_t started_ms_ = 0;
  bool started_ = false;
  uint32_t last_valid_distance_ms_ = 0;
  uint32_t target_since_ms_ = 0;
  uint32_t avoidance_started_ms_ = 0;
  uint32_t emitter_started_ms_ = 0;
  uint32_t emitter_cooldown_until_ms_ = 0;
};

}  // namespace robotlogic
