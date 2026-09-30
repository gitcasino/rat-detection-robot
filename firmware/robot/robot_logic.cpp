#include "robot_logic.h"

namespace robotlogic {

namespace {
constexpr TargetConfirmationMode kConfirmationMode = CFG_TARGET_CONFIRMATION;
}

Controller::Controller(const Timings &timings) : timings_(timings) {}

const char *Controller::state_name(RobotState state) {
  switch (state) {
    case RobotState::Idle:
      return "IDLE";
    case RobotState::TargetDetected:
      return "TARGET_DETECTED";
    case RobotState::Approaching:
      return "APPROACHING";
    case RobotState::ObstacleAvoidance:
      return "OBSTACLE_AVOIDANCE";
    case RobotState::EmitterActive:
      return "EMITTER_ACTIVE";
    case RobotState::Monitoring:
      return "MONITORING";
    case RobotState::Error:
      return "ERROR";
  }
  return "UNKNOWN";
}

const char *Controller::confirmation_name(TargetConfirmationMode mode) {
  switch (mode) {
    case TARGET_CONFIRM_FUSION:
      return "sensor_fusion";
    case TARGET_CONFIRM_DISTANCE_ONLY:
      return "distance_only";
    case TARGET_CONFIRM_DISABLED:
      return "disabled";
  }
  return "unknown";
}

bool Controller::confirm_activity(const Inputs &inputs) const {
  switch (kConfirmationMode) {
    case TARGET_CONFIRM_DISTANCE_ONLY:
      // Prototype behaviour. Deliberately labelled as proximity-only everywhere
      // it surfaces, because an object at 20 cm is not an identified rat.
      return in_range(inputs);
    case TARGET_CONFIRM_DISABLED:
      return false;
    case TARGET_CONFIRM_FUSION:
    default:
      break;
  }

  const bool vibration = inputs.vibration_configured && inputs.vibration_active;
  const bool infrared = inputs.ir_configured && inputs.ir_active;
#if CFG_REQUIRE_BOTH_CONFIRMATIONS
  return inputs.vibration_configured && inputs.ir_configured && vibration && infrared;
#else
  return vibration || infrared;
#endif
}

bool Controller::distance_usable(const Inputs &inputs) const {
  if (!inputs.distance_valid || inputs.distance_cm <= 0.0f) {
    return false;
  }
  return inputs.distance_cm <= timings_.max_usable_distance_cm;
}

bool Controller::in_range(const Inputs &inputs) const {
  return distance_usable(inputs) && inputs.distance_cm <= timings_.detect_distance_cm;
}

bool Controller::obstacle_present(const Inputs &inputs) const {
  return distance_usable(inputs) && inputs.distance_cm <= timings_.obstacle_clearance_cm;
}

bool Controller::faulted(const Inputs &inputs, uint32_t now_ms) const {
  // With neither the drive nor the emitter wired up there is no mission to run,
  // and staying in ERROR is more honest than pretending to monitor.
  if (!inputs.drive_ready && !inputs.emitter_ready) {
    return true;
  }
  // Every approach and emitter decision depends on the distance reading, so a
  // sensor that has gone quiet is surfaced instead of silently doing nothing.
  return (now_ms - last_valid_distance_ms_) > timings_.sensor_fault_ms;
}

Outputs Controller::make_outputs() const {
  Outputs outputs;
  outputs.state = state_;
  outputs.confirmation = confirmation_;
  outputs.emitter_request = emitter_active_;

  switch (state_) {
    case RobotState::Approaching:
      outputs.drive = DriveCommand::Forward;
      outputs.speed_percent = timings_.motor_speed_percent;
      break;
    case RobotState::ObstacleAvoidance:
      outputs.drive = DriveCommand::TurnRight;
      outputs.speed_percent = timings_.turn_speed_percent;
      break;
    case RobotState::EmitterActive:
      // Safety invariant: the chassis is stationary whenever the emitter is
      // driven. Repelling while rolling would make the output unpredictable.
      outputs.drive = DriveCommand::Stop;
      outputs.speed_percent = 0;
      break;
    default:
      outputs.drive = DriveCommand::Stop;
      outputs.speed_percent = 0;
      break;
  }
  return outputs;
}

StepResult Controller::emit(RobotState next, TransitionKind kind) {
  const RobotState previous = state_;
  state_ = next;

  StepResult result;
  result.outputs = make_outputs();
  result.has_transition = kind != TransitionKind::None;
  result.transition = Transition{kind, previous, next};
  return result;
}

StepResult Controller::emit(RobotState next, TransitionKind kind, TransitionKind secondary_kind) {
  StepResult result = emit(next, kind);
  result.has_secondary = true;
  result.secondary = Transition{secondary_kind, result.transition.from, next};
  return result;
}

StepResult Controller::update(const Inputs &inputs, uint32_t now_ms) {
  if (!started_) {
    started_ = true;
    started_ms_ = now_ms;
    last_valid_distance_ms_ = now_ms;
  }
  if (distance_usable(inputs)) {
    last_valid_distance_ms_ = now_ms;
  }

  const bool fault = faulted(inputs, now_ms);
  if (fault != faulted_) {
    faulted_ = fault;
    emitter_active_ = false;
    activity_confirmed_ = false;
    obstacle_active_ = false;
    confirmation_ = TARGET_CONFIRM_DISABLED;
    if (fault) {
      return emit(RobotState::Error, TransitionKind::Fault);
    }
    return emit(RobotState::Monitoring, TransitionKind::None);
  }
  if (faulted_) {
    StepResult result = emit(RobotState::Error, TransitionKind::None);
    result.outputs.emitter_request = false;
    return result;
  }

  const bool activity = confirm_activity(inputs);
  confirmation_ = activity ? kConfirmationMode : TARGET_CONFIRM_DISABLED;

  if (activity != activity_confirmed_) {
    activity_confirmed_ = activity;
    if (activity) {
      target_since_ms_ = now_ms;
      bursts_used_ = 0;
      emitter_cooldown_until_ms_ = now_ms;
      return emit(RobotState::TargetDetected, TransitionKind::TargetActivityDetected);
    }
    emitter_active_ = false;
    return emit(RobotState::Monitoring, TransitionKind::TargetActivityCleared);
  }

  const bool obstacle = obstacle_present(inputs);
  if (obstacle != obstacle_active_) {
    obstacle_active_ = obstacle;
    if (obstacle) {
      avoidance_started_ms_ = now_ms;
      return emit(RobotState::ObstacleAvoidance, TransitionKind::ObstacleDetected);
    }
    if (state_ == RobotState::ObstacleAvoidance) {
      return emit(activity && inputs.drive_ready ? RobotState::Approaching : RobotState::Monitoring,
                  TransitionKind::ObstacleCleared);
    }
  }

  switch (state_) {
    case RobotState::Idle:
    case RobotState::Monitoring:
      return emit(RobotState::Monitoring, TransitionKind::None);

    case RobotState::TargetDetected: {
      if ((now_ms - target_since_ms_) < timings_.settle_ms) {
        return emit(state_, TransitionKind::None);
      }
      if (inputs.drive_ready) {
        return emit(RobotState::Approaching, TransitionKind::None);
      }
      if (in_range(inputs)) {
        emitter_active_ = true;
        emitter_started_ms_ = now_ms;
        return emit(RobotState::EmitterActive, TransitionKind::EmitterActivated);
      }
      return emit(state_, TransitionKind::None);
    }

    case RobotState::Approaching:
      if (in_range(inputs)) {
        emitter_active_ = true;
        emitter_started_ms_ = now_ms;
        return emit(RobotState::EmitterActive, TransitionKind::EmitterActivated);
      }
      return emit(state_, TransitionKind::None);

    case RobotState::ObstacleAvoidance:
      if ((now_ms - avoidance_started_ms_) >= timings_.avoidance_ms) {
        if (in_range(inputs)) {
          // The obstacle cleared and the emitter armed in the same tick.
          emitter_active_ = true;
          emitter_started_ms_ = now_ms;
          return emit(RobotState::EmitterActive, TransitionKind::EmitterActivated,
                      TransitionKind::ObstacleCleared);
        }
        return emit(activity && inputs.drive_ready ? RobotState::Approaching : RobotState::Monitoring,
                    TransitionKind::ObstacleCleared);
      }
      return emit(state_, TransitionKind::None);

    case RobotState::EmitterActive: {
      if (!inputs.emitter_ready) {
        emitter_active_ = false;
        return emit(RobotState::Monitoring, TransitionKind::EmitterDeactivated);
      }

      const uint32_t elapsed = now_ms - emitter_started_ms_;
      if (emitter_active_ && elapsed < timings_.emitter_burst_ms) {
        return emit(state_, TransitionKind::None);
      }

      if (emitter_active_) {
        // Burst complete. Record the end of the activation window exactly once.
        emitter_active_ = false;
        bursts_used_ = static_cast<uint8_t>(bursts_used_ + 1);
        emitter_cooldown_until_ms_ = now_ms + timings_.emitter_cooldown_ms;
        return emit(state_, TransitionKind::EmitterDeactivated);
      }

      if (bursts_used_ >= timings_.max_bursts) {
        return emit(RobotState::Monitoring, TransitionKind::None);
      }
      if (in_range(inputs) && now_ms >= emitter_cooldown_until_ms_) {
        emitter_active_ = true;
        emitter_started_ms_ = now_ms;
        return emit(state_, TransitionKind::EmitterActivated);
      }
      return emit(state_, TransitionKind::None);
    }

    case RobotState::Error:
      break;
  }

  return emit(state_, TransitionKind::None);
}

}  // namespace robotlogic
