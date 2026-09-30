/*
 * Native test harness for the firmware control logic.
 *
 * The controller has no Arduino dependencies, so it can be compiled and run on a
 * workstation. This covers the decision logic the physical robot depends on:
 * confirmation rules, obstacle handling, emitter activation windows, the safety
 * latches and the fault path.
 *
 * Build and run (from the repository root):
 *     g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/robot \
 *         firmware/robot/robot_logic.cpp tools/firmware_logic_test.cpp \
 *         -o build/firmware_logic_test
 *     ./build/firmware_logic_test
 *
 * The Arduino IDE does not compile this file; it is a development tool.
 */

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "robot_logic.h"

namespace {

int g_failures = 0;
int g_checks = 0;

void check(bool condition, const std::string &label) {
  g_checks++;
  if (!condition) {
    g_failures++;
    std::printf("  FAIL  %s\n", label.c_str());
  }
}

using robotlogic::Controller;
using robotlogic::DriveCommand;
using robotlogic::Inputs;
using robotlogic::RobotState;
using robotlogic::StepResult;
using robotlogic::Timings;
using robotlogic::TransitionKind;

Timings test_timings() {
  Timings timings;
  timings.settle_ms = 100;
  timings.avoidance_ms = 200;
  timings.emitter_burst_ms = 500;
  timings.emitter_cooldown_ms = 400;
  timings.sensor_fault_ms = 1000;
  timings.max_bursts = 2;
  timings.detect_distance_cm = 20.0f;
  timings.obstacle_clearance_cm = 15.0f;
  return timings;
}

Inputs fused() {
  Inputs inputs;
  inputs.vibration_configured = true;
  inputs.ir_configured = true;
  inputs.drive_ready = true;
  inputs.emitter_ready = true;
  inputs.distance_valid = true;
  inputs.distance_cm = 120.0f;
  return inputs;
}

struct Harness {
  Controller controller{test_timings()};
  uint32_t now = 0;
  std::vector<robotlogic::TransitionKind> transitions;

  StepResult tick(Inputs inputs, uint32_t delta_ms = 10) {
    now += delta_ms;
    StepResult result = controller.update(inputs, now);
    if (result.has_transition && result.transition.kind != TransitionKind::None) {
      transitions.push_back(result.transition.kind);
    }
    if (result.has_secondary && result.secondary.kind != TransitionKind::None) {
      transitions.push_back(result.secondary.kind);
    }
    return result;
  }

  bool saw(TransitionKind kind) const {
    for (TransitionKind item : transitions) {
      if (item == kind) {
        return true;
      }
    }
    return false;
  }

  size_t count(TransitionKind kind) const {
    size_t total = 0;
    for (TransitionKind item : transitions) {
      if (item == kind) {
        total++;
      }
    }
    return total;
  }
};

void test_monitoring_is_the_resting_state() {
  Harness harness;
  Inputs inputs = fused();

  for (int i = 0; i < 50; i++) {
    harness.tick(inputs);
  }

  check(harness.controller.state() == RobotState::Monitoring, "resting state is MONITORING");
  check(!harness.controller.emitter_active(), "emitter stays off while monitoring");
  check(harness.saw(TransitionKind::None) || harness.transitions.empty(), "no spurious transitions");
}

void test_object_alone_does_not_confirm_activity() {
  Harness harness;
  Inputs inputs = fused();
  inputs.vibration_configured = false;
  inputs.ir_configured = false;

  for (int i = 0; i < 40; i++) {
    harness.tick(inputs);
  }

  check(!harness.saw(TransitionKind::TargetActivityDetected),
        "an object in range is not target activity without sensor confirmation");
  check(!harness.controller.emitter_active(), "emitter never fires on proximity alone");
  check(harness.controller.state() == RobotState::Monitoring, "state stays MONITORING");
}

void test_vibration_confirms_and_emitter_fires_once() {
  Timings timings = test_timings();
  timings.max_bursts = 1;
  Harness harness{Controller{timings}, 0, {}};
  Inputs inputs = fused();
  inputs.vibration_active = true;
  inputs.distance_cm = 18.0f;

  StepResult activating;
  for (int i = 0; i < 60; i++) {
    StepResult result = harness.tick(inputs, 20);
    if (result.has_transition && result.transition.kind == TransitionKind::EmitterActivated) {
      activating = result;
    }
  }

  check(harness.saw(TransitionKind::TargetActivityDetected), "activity is declared once");
  check(activating.outputs.emitter_request, "activation requests the emitter");
  check(activating.outputs.state == RobotState::EmitterActive, "state becomes EMITTER_ACTIVE");
  check(activating.outputs.drive == DriveCommand::Stop, "robot stops while emitting");

  // One burst must produce exactly one activation and one deactivation event.
  check(harness.count(TransitionKind::EmitterActivated) == 1, "a burst emits EMITTER_ACTIVATED once");
  check(harness.count(TransitionKind::EmitterDeactivated) == 1, "a burst emits EMITTER_DEACTIVATED once");
  check(!harness.controller.emitter_active(), "emitter returns to inactive after the burst");
}

void test_emitter_respects_cooldown_between_bursts() {
  Timings timings = test_timings();
  timings.max_bursts = 3;
  Harness harness{Controller{timings}, 0, {}};

  Inputs inputs = fused();
  inputs.vibration_active = true;
  inputs.distance_cm = 18.0f;

  uint32_t burst_starts = 0;
  uint32_t previous = 0;
  for (int i = 0; i < 400; i++) {
    uint32_t before = harness.now;
    StepResult result = harness.tick(inputs, 10);
    if (result.has_transition && result.transition.kind == TransitionKind::EmitterActivated) {
      if (previous != 0) {
        check(harness.now - previous >= timings.emitter_burst_ms + timings.emitter_cooldown_ms,
              "consecutive bursts are separated by the cooldown");
      }
      previous = harness.now;
      burst_starts++;
    }
    (void)before;
  }

  check(burst_starts == 3, "burst count is capped by max_bursts");
  check(harness.controller.bursts_used() == 3, "burst counter matches emitted bursts");
  check(harness.count(TransitionKind::EmitterActivated) == 3, "no more activations than bursts");
}

void test_activity_clear_deactivates_the_emitter() {
  Harness harness;
  Inputs inputs = fused();
  inputs.vibration_active = true;
  inputs.distance_cm = 18.0f;

  for (int i = 0; i < 12; i++) {
    harness.tick(inputs, 20);
  }
  check(harness.controller.emitter_active(), "emitter is active before the target clears");

  inputs.vibration_active = false;
  StepResult cleared = harness.tick(inputs, 20);

  check(cleared.has_transition, "clearing activity produces a transition");
  check(cleared.transition.kind == TransitionKind::TargetActivityCleared, "transition is TARGET_ACTIVITY_CLEARED");
  check(!cleared.outputs.emitter_request, "emitter command is dropped immediately");
  check(cleared.outputs.state == RobotState::Monitoring, "robot returns to MONITORING");
}

void test_obstacle_interrupts_an_approach() {
  Harness harness;
  Inputs inputs = fused();
  inputs.vibration_active = true;

  for (int i = 0; i < 20; i++) {
    StepResult result = harness.tick(inputs, 20);
    if (result.transition.kind == TransitionKind::None && result.outputs.state == RobotState::Approaching) {
      check(result.outputs.drive == DriveCommand::Forward, "approach drives forward");
    }
  }
  check(harness.controller.state() == RobotState::Approaching, "robot advances towards the activity");

  inputs.distance_cm = 8.0f;
  StepResult obstacle = harness.tick(inputs, 20);

  check(obstacle.transition.kind == TransitionKind::ObstacleDetected, "obstacle is reported");
  check(obstacle.outputs.state == RobotState::ObstacleAvoidance, "state becomes OBSTACLE_AVOIDANCE");
  check(obstacle.outputs.drive == DriveCommand::TurnRight, "robot turns away instead of driving on");
  check(!obstacle.outputs.emitter_request, "emitter stays off while avoiding");

  StepResult cleared = harness.tick(inputs, 20);
  (void)cleared;
  check(!harness.controller.emitter_active(), "avoidance never triggers the emitter");
}

void test_obstacle_inside_range_still_repels_but_never_while_moving() {
  Timings timings = test_timings();
  timings.max_bursts = 1;
  Harness harness{Controller{timings}, 0, {}};
  Inputs inputs = fused();
  inputs.vibration_active = true;
  inputs.distance_cm = 8.0f;

  bool emitted_while_moving = false;
  for (int i = 0; i < 200; i++) {
    StepResult result = harness.tick(inputs, 20);
    if (result.outputs.emitter_request && result.outputs.drive != DriveCommand::Stop) {
      emitted_while_moving = true;
    }
  }

  check(harness.saw(TransitionKind::ObstacleDetected), "an object inside clearance is an obstacle");
  check(harness.saw(TransitionKind::EmitterActivated), "confirmed activity inside range still repels");
  check(!emitted_while_moving, "the emitter is never driven while the chassis is moving");
}

void test_missing_hardware_fails_safe() {
  Controller controller{test_timings()};
  Inputs inputs = fused();
  inputs.drive_ready = false;
  inputs.emitter_ready = false;
  inputs.vibration_active = true;

  StepResult result = controller.update(inputs, 0);
  StepResult second = controller.update(inputs, 50);

  check(result.transition.kind == TransitionKind::Fault, "unwired drive and emitter raise a fault");
  check(result.outputs.state == RobotState::Error, "state becomes ERROR");
  check(result.outputs.drive == DriveCommand::Stop, "drive is stopped");
  check(result.outputs.emitter_request == false, "emitter command is inactive");
  check(!second.has_transition, "the fault is reported once, not every tick");
}

void test_distance_sensor_loss_raises_a_fault() {
  Timings timings = test_timings();
  Controller controller{timings};
  Inputs inputs = fused();

  for (uint32_t t = 0; t <= timings.sensor_fault_ms; t += 50) {
    controller.update(inputs, t);
  }
  inputs.distance_valid = false;
  StepResult result = controller.update(inputs, timings.sensor_fault_ms * 2 + 100);

  check(result.outputs.state == RobotState::Error, "silent distance sensor faults the controller");
  check(!result.outputs.emitter_request, "no emission without a distance reading");
}

void test_emitter_only_build_never_drives() {
  Harness harness;
  Inputs inputs = fused();
  inputs.drive_ready = false;
  inputs.vibration_active = true;
  inputs.distance_cm = 18.0f;

  bool moved = false;
  for (int i = 0; i < 40; i++) {
    StepResult result = harness.tick(inputs, 20);
    if (result.outputs.drive != DriveCommand::Stop) {
      moved = true;
    }
  }
  check(!moved, "an emitter-only build never commands motion");
  check(harness.saw(TransitionKind::EmitterActivated), "emitter-only build still repels in range");
}

void test_obstacle_cleared_resumes_approach() {
  Harness harness;
  Inputs inputs = fused();
  inputs.vibration_active = true;

  for (int i = 0; i < 15; i++) {
    harness.tick(inputs, 20);
  }
  inputs.distance_cm = 6.0f;
  harness.tick(inputs, 20);
  inputs.distance_cm = 100.0f;
  StepResult resumed = harness.tick(inputs, 300);

  check(resumed.outputs.drive == DriveCommand::Forward, "approach resumes once the path clears");
  check(harness.saw(TransitionKind::ObstacleCleared), "clearing is reported");
}

}  // namespace

int main() {
  test_monitoring_is_the_resting_state();
  test_object_alone_does_not_confirm_activity();
  test_vibration_confirms_and_emitter_fires_once();
  test_emitter_respects_cooldown_between_bursts();
  test_activity_clear_deactivates_the_emitter();
  test_obstacle_interrupts_an_approach();
  test_obstacle_inside_range_still_repels_but_never_while_moving();
  test_missing_hardware_fails_safe();
  test_distance_sensor_loss_raises_a_fault();
  test_emitter_only_build_never_drives();
  test_obstacle_cleared_resumes_approach();

  std::printf("%s  %d checks, %d failures\n", g_failures == 0 ? "PASS" : "FAIL", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
