# Expected generated code for Action Execution initialization

These examples omit generated code unrelated to Action Execution initialization.
The Define source and generated Python shown here are canonical. Before an
intentional codegen change alters them, update the affected example as part of
the design change. The governing representation principles are in the
[literal Python execution codegen design](execution_codegen_design.md).

## Empty Rule arrival before a callee's Action Parent Create

Source for `test/__init__.py` (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it also assigns the action</runner>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in action</runner>::position<run>.
        destroy the particle in action</runner>::position<run>.
    }
}
```

Expected `__main__.py` and `test/__init__.py`:

```python
def main():
    literal.start(Test)


class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(self, scheduler)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.execution_action_runner = (
            local.my_domain_com.my_lib.runner.RunnerExecution(
                self.scheduler,
            )
        )

    def on_action_parent_occupied(self):
        self.scheduler.submit(
            self.create_action_runner__position_run
        )
        self.execution_action_runner.on_action_parent_occupied()

    def create_action_runner__position_run(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<run>"
        ).destroy_particle()
```

Source for `runner/__init__.py` (`runner.dfn`):

```define
define the potential action<my.domain.com:my_lib:/runner> {
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<wrapper> {
            it may only contain particles where {
                it has the action</middle>.
            }
        }
        create a particle in position<wrapper>.
        create a particle in position<wrapper>::action</middle>::position<box>.
        create a particle in position<wrapper>::action</middle>::position<run>.
    }
}
```

Expected `runner/__init__.py`:

```python
@final
class RunnerExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_wrapper = literal.LocalPosition(
            "position<wrapper>",
            constraints=(local.my_domain_com.my_lib.middle.Middle,),
            scheduler=self.scheduler,
        )
        self.execution_position_wrapper__action_middle: (
            local.my_domain_com.my_lib.middle.MiddleExecution
        )
        self.join_for_destroy_position_wrapper = self.scheduler.create_join(3)

    def on_action_parent_occupied(self):
        self.create_position_wrapper()

    def create_position_wrapper(self):
        self.local_position_wrapper.create_particle()
        self.execution_position_wrapper__action_middle = (
            local.my_domain_com.my_lib.middle.MiddleExecution(
                self.local_position_wrapper.particle.get_action(
                    local.my_domain_com.my_lib.middle.Middle
                ),
                self.scheduler,
            )
        )
        self.execution_position_wrapper__action_middle.join_when_empty_position_box__action_worker__position_output = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.join_when_empty_position_final = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.join_for_empty_rule_position_box = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.join_for_move_position_box__action_worker__position_output_to_position_final = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.join_for_destroy_position_box = self.scheduler.create_join(2)
        self.execution_position_wrapper__action_middle.join_for_destroy_position_run = literal.NO_JOIN
        self.execution_position_wrapper__action_middle.guarantees.position_final.consumers.append(
            self.destroy_position_wrapper__action_middle__position_final
        )
        self.execution_position_wrapper__action_middle.guarantees.position_box.consumers.append(
            self.destroy_position_wrapper
        )
        self.execution_position_wrapper__action_middle.guarantees.position_run.consumers.append(
            self.destroy_position_wrapper
        )
        self.scheduler.submit(
            self.create_position_wrapper__action_middle__position_box
        )
        self.create_position_wrapper__action_middle__position_run()

    def create_position_wrapper__action_middle__position_box(self):
        self.local_position_wrapper.particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<box>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.init_when_occupied_position_box()
        # This caller resolves Worker's Empty Rule to one remaining arrival.
        self.execution_position_wrapper__action_middle.execution_position_box__action_worker.join_for_empty_rule_position_input = literal.NO_JOIN
        self.scheduler.submit(
            self.execution_position_wrapper__action_middle.accept_when_occupied_position_box
        )

    def create_position_wrapper__action_middle__position_run(self):
        self.local_position_wrapper.particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.accept_for_empty_rule_position_run()

    def destroy_position_wrapper__action_middle__position_final(self):
        self.local_position_wrapper.particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<final>"
        ).destroy_particle()
        self.destroy_position_wrapper()

    def destroy_position_wrapper(self):
        if not self.join_for_destroy_position_wrapper.arrive():
            return
        self.local_position_wrapper.destroy_particle()
```

Source for `middle/__init__.py` (`middle.dfn`):

```define
define the potential action<my.domain.com:my_lib:/middle> {
    define the position<run>.
    define the position<box> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    define the position<final>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<box>::action</worker>::position<input>.
        create a particle in position<box>::action</worker>::position<run>.
        move the particle in position<box>::action</worker>::position<output> to position<final>.
        destroy the particle in position<box>.
        destroy the particle in position<run>.
    }
}
```

Expected `middle/__init__.py`:

```python
@final
class MiddleGuarantees:
    def __init__(self):
        self.position_final = literal.Guarantee()
        self.position_box = literal.Guarantee()
        self.position_run = literal.Guarantee()


@final
class MiddleExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MiddleGuarantees()
        self.destruction_connections = destruction_connections
        self.execution_position_box__action_worker: (
            local.my_domain_com.my_lib.worker.WorkerExecution
        )
        self.join_for_move_position_box__action_worker__position_output_to_position_final: literal.Join
        self.join_for_destroy_position_box: literal.Join

    def accept_when_occupied_position_box(self):
        self.scheduler.submit(
            self.create_position_box__action_worker__position_input
        )
        self.create_position_box__action_worker__position_run()

    def init_when_occupied_position_box(self):
        self.execution_position_box__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.action.get_interface_position(
                    "position<box>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_box__action_worker.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_box__action_worker.join_for_move_position_input_to_position_output = literal.NO_JOIN
        self.execution_position_box__action_worker.join_for_destroy_position_run = literal.NO_JOIN
        self.execution_position_box__action_worker.guarantees.position_input__move__position_output.consumers.append(
            self.move_position_box__action_worker__position_output_to_position_final
        )
        self.execution_position_box__action_worker.guarantees.position_run.consumers.append(
            self.destroy_position_box
        )

    def create_position_box__action_worker__position_input(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<input>"
        ).create_particle()
        self.execution_position_box__action_worker.accept_for_empty_rule_position_input()

    def create_position_box__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_box__action_worker.accept_for_empty_rule_position_run()

    def move_position_box__action_worker__position_output_to_position_final(self):
        if not self.join_for_move_position_box__action_worker__position_output_to_position_final.arrive():
            return
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<output>"
        ).move_particle_to(
            self.action.get_interface_position("position<final>")
        )
        self.guarantees.position_final.publish(
            self.scheduler,
            self.destroy_position_box,
        )

    def destroy_position_box(self):
        if not self.join_for_destroy_position_box.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_box)

    def continue_destroy_position_box(self):
        self.action.get_interface_position("position<box>").destroy_particle()
        self.guarantees.position_box.publish(self.scheduler)
```

Source for `worker/__init__.py` (`worker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<run>.
    define the position<input>.
    define the position<output>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        move the particle in position<input> to position<output>.
        destroy the particle in position<run>.
    }
}
```

Expected `worker/__init__.py`:

```python
@final
class WorkerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.destruction_connections = destruction_connections
        self.join_for_move_position_input_to_position_output: literal.Join
        self.join_for_empty_rule_position_input: literal.Join

    def accept_for_empty_rule_position_input(self):
        if not self.join_for_empty_rule_position_input.arrive():
            return
        self.move_position_input_to_position_output()

    def move_position_input_to_position_output(self):
        if not self.join_for_move_position_input_to_position_output.arrive():
            return
        self.action.get_interface_position(
            "position<input>"
        ).move_particle_to(
            self.action.get_interface_position("position<output>")
        )
        self.guarantees.position_input__move__position_output.publish(
            self.scheduler
        )
```

## Actions assigned to particles in local positions

Source for `test/__init__.py` (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<runner_parent> {
            it may only contain particles where {
                it has the action</runner>.
            }
        }
        create a particle in position<runner_parent>.
        create a particle in position<runner_parent>::action</runner>::position<second>.
        create a particle in position<runner_parent>::action</runner>::position<first>.
    }
}
```

Expected `__main__.py` and `test/__init__.py`:

```python
def main():
    literal.start(Test)


class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(scheduler)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(
        self,
        scheduler: literal.Scheduler,
    ):
        self.scheduler = scheduler
        self.local_position_runner_parent = literal.LocalPosition(
            "position<runner_parent>",
            constraints=(local.my_domain_com.my_lib.runner.Runner,),
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_runner_parent = self.scheduler.create_join(2)

    def on_action_parent_occupied(self):
        self.create_position_runner_parent()

    def create_position_runner_parent(self):
        self.local_position_runner_parent.create_particle()
        self.execution_position_runner_parent__action_runner = (
            local.my_domain_com.my_lib.runner.RunnerExecution(
                self.local_position_runner_parent.particle.get_action(
                    local.my_domain_com.my_lib.runner.Runner
                ),
                self.scheduler,
            )
        )
        self.execution_position_runner_parent__action_runner.join_for_empty_rule_position_first = literal.NO_JOIN
        self.execution_position_runner_parent__action_runner.join_for_empty_rule_position_second = literal.NO_JOIN
        self.execution_position_runner_parent__action_runner.join_for_move_position_first_to_position_first_result = literal.NO_JOIN
        self.execution_position_runner_parent__action_runner.join_for_move_position_second_to_position_second_result = literal.NO_JOIN
        self.execution_position_runner_parent__action_runner.guarantees.position_second__move__position_second_result.consumers.append(
            self.destroy_position_runner_parent__action_runner__position_second_result
        )
        self.execution_position_runner_parent__action_runner.guarantees.position_first__move__position_first_result.consumers.append(
            self.destroy_position_runner_parent__action_runner__position_first_result
        )
        self.scheduler.submit(
            self.create_position_runner_parent__action_runner__position_second
        )
        self.create_position_runner_parent__action_runner__position_first()

    def create_position_runner_parent__action_runner__position_first(self):
        self.local_position_runner_parent.particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<first>"
        ).create_particle()
        self.execution_position_runner_parent__action_runner.accept_for_empty_rule_position_first()

    def create_position_runner_parent__action_runner__position_second(self):
        self.local_position_runner_parent.particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<second>"
        ).create_particle()
        self.execution_position_runner_parent__action_runner.accept_for_empty_rule_position_second()

    def destroy_position_runner_parent__action_runner__position_first_result(self):
        self.local_position_runner_parent.particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<first_result>"
        ).destroy_particle()
        self.destroy_position_runner_parent()

    def destroy_position_runner_parent__action_runner__position_second_result(self):
        self.local_position_runner_parent.particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<second_result>"
        ).destroy_particle()
        self.destroy_position_runner_parent()

    def destroy_position_runner_parent(self):
        if not self.join_for_destroy_position_runner_parent.arrive():
            return
        self.local_position_runner_parent.destroy_particle()
```

Source for `runner/__init__.py` (`runner.dfn`):

```define
define the potential action<my.domain.com:my_lib:/runner> {
    define the position<first>.
    define the position<second>.
    define the position<first_result>.
    define the position<second_result>.
    it happens when {
        the position<first> has a particle.
    } and it does {
        move the particle in position<first> to position<first_result>.
        move the particle in position<second> to position<second_result>.
    }
}
```

Expected `runner/__init__.py`:

```python
@final
class RunnerGuarantees:
    def __init__(self):
        self.position_first__move__position_first_result = literal.Guarantee()
        self.position_second__move__position_second_result = literal.Guarantee()


@final
class RunnerExecution:
    def __init__(
        self,
        action: Runner,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = RunnerGuarantees()
        self.join_for_move_position_first_to_position_first_result: literal.Join
        self.join_for_move_position_second_to_position_second_result: literal.Join
        self.join_for_empty_rule_position_first: literal.Join
        self.join_for_empty_rule_position_second: literal.Join

    def accept_for_empty_rule_position_first(self):
        if not self.join_for_empty_rule_position_first.arrive():
            return
        self.move_position_first_to_position_first_result()

    def accept_for_empty_rule_position_second(self):
        if not self.join_for_empty_rule_position_second.arrive():
            return
        self.move_position_second_to_position_second_result()

    def move_position_first_to_position_first_result(self):
        if not self.join_for_move_position_first_to_position_first_result.arrive():
            return
        self.action.get_interface_position(
            "position<first>"
        ).move_particle_to(
            self.action.get_interface_position("position<first_result>")
        )
        self.guarantees.position_first__move__position_first_result.publish(
            self.scheduler
        )

    def move_position_second_to_position_second_result(self):
        if not self.join_for_move_position_second_to_position_second_result.arrive():
            return
        self.action.get_interface_position(
            "position<second>"
        ).move_particle_to(
            self.action.get_interface_position("position<second_result>")
        )
        self.guarantees.position_second__move__position_second_result.publish(
            self.scheduler
        )
```

## Destructor initialization before its child Requirement is satisfied

Supporting Position definition (`marker.dfn`):

```define
define the potential position<my.domain.com:my_lib:/marker>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<box> {
            it may only contain particles where {
                it has the action</maker>.
            }
        }
        create a particle in position<box>.
        create a particle in position<box>::action</maker>::position<run>.
        destroy the particle in position<box>::action</maker>::position<result>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_box = literal.LocalPosition(
            "position<box>",
            constraints=(local.my_domain_com.my_lib.maker.Maker,),
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_box = self.scheduler.create_join(2)

    def create_position_box(self):
        self.local_position_box.create_particle()
        self.execution_position_box__action_maker = (
            local.my_domain_com.my_lib.maker.MakerExecution(
                self.local_position_box.particle.get_action(
                    local.my_domain_com.my_lib.maker.Maker
                ),
                self.scheduler,
            )
        )
        # The result Guarantee makes the Destructor's Action Parent available.
        self.execution_position_box__action_maker.guarantees.position_result.inits.append(
            self.init_position_box__action_maker__position_result
        )
        self.scheduler.submit(
            self.create_position_box__action_maker__position_run
        )
        self.execution_position_box__action_maker.accept_when_empty_position_result()

    def create_position_box__action_maker__position_run(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).destroy_particle()
        self.destroy_position_box()

    def init_position_box__action_maker__position_result(self):
        self.execution_position_box__action_maker__position_result__action_destructor = (
            local.my_domain_com.my_lib.destructor.DestructorExecution(
                self.local_position_box.particle.get_action(
                    local.my_domain_com.my_lib.maker.Maker
                ).get_interface_position(
                    "position<result>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.destructor.Destructor
                ),
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker__position_result__action_destructor.join_for_empty_rule_global_position_marker = literal.NO_JOIN
        self.execution_position_box__action_maker__position_result__action_destructor.join_for_move_global_position_marker_to_position_holder = literal.NO_JOIN
        self.execution_position_box__action_maker__position_result__action_destructor.guarantees.global_position_marker.consumers.append(
            self.destroy_position_box__action_maker__position_result__global_position_marker
        )
        self.execution_position_box__action_maker.guarantees.position_result__global_position_marker.consumers.append(
            self.accept_guarantee_position_box__action_maker__position_result__action_destructor
        )

    def accept_guarantee_position_box__action_maker__position_result__action_destructor(self):
        self.execution_position_box__action_maker__position_result__action_destructor.accept_for_empty_rule_global_position_marker()

    def destroy_position_box__action_maker__position_result__global_position_marker(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<result>"
        ).particle.get_position(
            local.my_domain_com.my_lib.marker.Marker
        ).destroy_particle()
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<result>"
        ).destroy_particle()
        self.destroy_position_box()

    def destroy_position_box(self):
        if not self.join_for_destroy_position_box.arrive():
            return
        self.local_position_box.destroy_particle()
```

Source (`maker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/maker> {
    define the position<result> {
        it may only contain particles where {
            it has the action</destructor>.
            it has the position</marker>.
        }
    }
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<result>.
        create a particle in position<result>::position</marker>.
    }
}
```

Expected generated `maker/__init__.py`:

```python
@final
class MakerGuarantees:
    def __init__(self):
        self.position_result = literal.Guarantee()
        self.position_result__global_position_marker = (
            literal.Guarantee()
        )


@final
class MakerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MakerGuarantees()

    def accept_when_empty_position_result(self):
        self.create_position_result()

    def create_position_result(self):
        self.action.get_interface_position(
            "position<result>"
        ).create_particle()
        self.guarantees.position_result.publish(
            self.scheduler,
            self.create_position_result__global_position_marker,
        )

    def create_position_result__global_position_marker(self):
        self.action.get_interface_position(
            "position<result>"
        ).particle.get_position(
            local.my_domain_com.my_lib.marker.Marker
        ).create_particle()
        self.guarantees.position_result__global_position_marker.publish(
            self.scheduler
        )
```

Source (`destructor.dfn`):

```define
define the potential action<my.domain.com:my_lib:/destructor> {
    it also assigns the position</marker>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<holder>.
        move the particle in position</marker> to position<holder>.
        move the particle in position<holder> to position</marker>.
    }
}
```

Expected generated `destructor/__init__.py`:

```python
@final
class DestructorGuarantees:
    def __init__(self):
        self.global_position_marker = literal.Guarantee()


@final
class DestructorExecution:
    def __init__(
        self,
        action: Destructor,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = DestructorGuarantees()
        self.local_position_holder = literal.LocalPosition(
            "position<holder>",
            scheduler=self.scheduler,
        )
        self.join_for_move_global_position_marker_to_position_holder: literal.Join
        self.join_for_empty_rule_global_position_marker: literal.Join

    def accept_for_empty_rule_global_position_marker(self):
        if not self.join_for_empty_rule_global_position_marker.arrive():
            return
        self.move_global_position_marker_to_position_holder()

    def move_global_position_marker_to_position_holder(self):
        if not self.join_for_move_global_position_marker_to_position_holder.arrive():
            return
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.marker.Marker
        ).move_particle_to(self.local_position_holder)
        self.local_position_holder.move_particle_to(
            self.action.on_particle.get_position(
                local.my_domain_com.my_lib.marker.Marker
            )
        )
        self.guarantees.global_position_marker.publish(
            self.scheduler
        )
```

## One Binding Hole releases every kind of consumer

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</middle>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</middle>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</middle>::position<trigger_pos>.
    }
}
```

Expected generated `__main__.py` and `test/__init__.py`:

```python
def main():
    literal.start(Test)


class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(scheduler)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(
        self,
        scheduler: literal.Scheduler,
    ):
        self.scheduler = scheduler
        self.local_position_gateway = literal.LocalPosition(
            "position<gateway>",
            constraints=(local.my_domain_com.my_lib.middle.Middle,),
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        self.create_position_gateway()

    def create_position_gateway(self):
        self.local_position_gateway.create_particle()
        self.execution_position_gateway__action_middle = (
            local.my_domain_com.my_lib.middle.MiddleExecution(
                self.local_position_gateway.particle.get_action(
                    local.my_domain_com.my_lib.middle.Middle
                ),
                self.scheduler,
            )
        )
        self.scheduler.submit(
            self.create_position_gateway__action_middle__position_trigger_pos
        )
        self.execution_position_gateway__action_middle.on_action_parent_occupied()

    def create_position_gateway__action_middle__position_trigger_pos(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        self.local_position_gateway.destroy_particle()
```

Source (`middle.dfn`):

```define
define the potential action<my.domain.com:my_lib:/middle> {
    it also assigns the action</child_a>.
    it also assigns the action</child_b>.
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<first>.
        define the position<second>.
        create a particle in position<first>.
        create a particle in position<second>.
        create a particle in action</child_a>::position<trigger_pos>.
        create a particle in action</child_b>::position<trigger_pos>.
        destroy the particle in action</child_a>::position<trigger_pos>.
        destroy the particle in action</child_b>::position<trigger_pos>.
    }
}
```

Expected generated `middle/__init__.py`:

```python
@final
class MiddleExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.local_position_first = literal.LocalPosition(
            "position<first>",
            scheduler=self.scheduler,
        )
        self.local_position_second = literal.LocalPosition(
            "position<second>",
            scheduler=self.scheduler,
        )
        self.execution_action_child_a = (
            local.my_domain_com.my_lib.child_a.ChildAExecution(
                self.scheduler,
            )
        )
        self.execution_action_child_b = (
            local.my_domain_com.my_lib.child_b.ChildBExecution(
                self.scheduler,
            )
        )

    def on_action_parent_occupied(self):
        self.scheduler.submit(self.create_position_first)
        self.scheduler.submit(self.create_position_second)
        self.scheduler.submit(self.create_action_child_a__position_trigger_pos)
        self.scheduler.submit(self.create_action_child_b__position_trigger_pos)
        self.scheduler.submit(self.execution_action_child_a.on_action_parent_occupied)
        self.execution_action_child_b.on_action_parent_occupied()

    def create_position_first(self):
        self.local_position_first.create_particle()
        self.local_position_first.destroy_particle()

    def create_position_second(self):
        self.local_position_second.create_particle()
        self.local_position_second.destroy_particle()

    def create_action_child_a__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.child_a.ChildA
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.child_a.ChildA
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()

    def create_action_child_b__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.child_b.ChildB
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.child_b.ChildB
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
```

Source (`child_a.dfn`):

```define
define the potential action<my.domain.com:my_lib:/child_a> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
    }
}
```

Expected generated `child_a/__init__.py`:

```python
class ChildA(literal.Action):
    def __init__(self, on_particle: literal.Particle):
        super().__init__(
            on_particle,
            interface_positions=[
                literal.LocalPosition(
                    "position<trigger_pos>",
                    scheduler=on_particle.scheduler,
                ),
            ],
        )


@final
class ChildAExecution:
    def __init__(self, scheduler: literal.Scheduler):
        self.scheduler = scheduler
        self.local_position_scratch = literal.LocalPosition(
            "position<scratch>",
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        self.create_position_scratch()

    def create_position_scratch(self):
        self.local_position_scratch.create_particle()
        self.local_position_scratch.destroy_particle()
```

Source (`child_b.dfn`):

```define
define the potential action<my.domain.com:my_lib:/child_b> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
    }
}
```

Expected generated `child_b/__init__.py`:

```python
class ChildB(literal.Action):
    def __init__(self, on_particle: literal.Particle):
        super().__init__(
            on_particle,
            interface_positions=[
                literal.LocalPosition(
                    "position<trigger_pos>",
                    scheduler=on_particle.scheduler,
                ),
            ],
        )


@final
class ChildBExecution:
    def __init__(self, scheduler: literal.Scheduler):
        self.scheduler = scheduler
        self.local_position_scratch = literal.LocalPosition(
            "position<scratch>",
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        self.create_position_scratch()

    def create_position_scratch(self):
        self.local_position_scratch.create_particle()
        self.local_position_scratch.destroy_particle()
```

## One Guarantee initializes multiple Destructor executions

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<box> {
            it may only contain particles where {
                it has the action</maker>.
            }
        }
        create a particle in position<box>.
        create a particle in position<box>::action</maker>::position<run>.
        destroy the particle in position<box>::action</maker>::position<result>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_box = literal.LocalPosition(
            "position<box>",
            constraints=(local.my_domain_com.my_lib.maker.Maker,),
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_box = self.scheduler.create_join(2)

    def create_position_box(self):
        self.local_position_box.create_particle()
        self.execution_position_box__action_maker = (
            local.my_domain_com.my_lib.maker.MakerExecution(
                self.local_position_box.particle.get_action(
                    local.my_domain_com.my_lib.maker.Maker
                ),
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker.guarantees.position_result.inits.append(
            self.init_position_box__action_maker__position_result
        )
        # The Destroy and both Destructor branches have the same preceding
        # Create and no dependencies on one another.
        self.execution_position_box__action_maker.guarantees.position_result.consumers.append(
            self.destroy_position_box__action_maker__position_result
        )
        self.scheduler.submit(
            self.create_position_box__action_maker__position_run
        )
        self.execution_position_box__action_maker.accept_when_empty_position_result()

    def create_position_box__action_maker__position_run(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).destroy_particle()
        self.destroy_position_box()

    def init_position_box__action_maker__position_result(self):
        # This one Guarantee init inits both Destructor Action Executions before
        # its consumers run.
        self.execution_position_box__action_maker__position_result__action_destruct_b = (
            local.my_domain_com.my_lib.destruct_b.DestructBExecution(
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker.guarantees.position_result.consumers.append(
            self.accept_guarantee_position_box__action_maker__position_result__action_destruct_b
        )
        self.execution_position_box__action_maker__position_result__action_destruct_a = (
            local.my_domain_com.my_lib.destruct_a.DestructAExecution(
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker.guarantees.position_result.consumers.append(
            self.accept_guarantee_position_box__action_maker__position_result__action_destruct_a
        )

    def accept_guarantee_position_box__action_maker__position_result__action_destruct_b(self):
        self.execution_position_box__action_maker__position_result__action_destruct_b.on_action_parent_occupied()

    def accept_guarantee_position_box__action_maker__position_result__action_destruct_a(self):
        self.execution_position_box__action_maker__position_result__action_destruct_a.on_action_parent_occupied()

    def destroy_position_box__action_maker__position_result(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<result>"
        ).destroy_particle()
        self.destroy_position_box()

    def destroy_position_box(self):
        if not self.join_for_destroy_position_box.arrive():
            return
        self.local_position_box.destroy_particle()
```

Source (`maker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/maker> {
    define the position<result> {
        it may only contain particles where {
            it has the action</destruct_a>.
            it has the action</destruct_b>.
        }
    }
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<result>.
    }
}
```

Expected generated `maker/__init__.py`:

```python
@final
class MakerGuarantees:
    def __init__(self):
        self.position_result = literal.Guarantee()


@final
class MakerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MakerGuarantees()

    def accept_when_empty_position_result(self):
        self.create_position_result()

    def create_position_result(self):
        self.action.get_interface_position(
            "position<result>"
        ).create_particle()
        self.guarantees.position_result.publish(
            self.scheduler
        )
```

Source (`destruct_a.dfn`):

```define
define the potential action<my.domain.com:my_lib:/destruct_a> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<_noop>.
        create a particle in position<_noop>.
        destroy the particle in position<_noop>.
    }
}
```

Expected generated `destruct_a/__init__.py`:

```python
class DestructA(literal.Action):
    pass


@final
class DestructAExecution:
    def __init__(self, scheduler: literal.Scheduler):
        self.scheduler = scheduler
        self.local_position__noop = literal.LocalPosition(
            "position<_noop>",
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        self.create_position_noop()

    def create_position_noop(self):
        self.local_position__noop.create_particle()
        self.local_position__noop.destroy_particle()
```

Source (`destruct_b.dfn`):

```define
define the potential action<my.domain.com:my_lib:/destruct_b> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<_noop>.
        create a particle in position<_noop>.
        destroy the particle in position<_noop>.
    }
}
```

Expected generated `destruct_b/__init__.py`:

```python
class DestructB(literal.Action):
    pass


@final
class DestructBExecution:
    def __init__(self, scheduler: literal.Scheduler):
        self.scheduler = scheduler
        self.local_position__noop = literal.LocalPosition(
            "position<_noop>",
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        self.create_position_noop()

    def create_position_noop(self):
        self.local_position__noop.create_particle()
        self.local_position__noop.destroy_particle()
```

## An ordinary Action Execution initialized after a callee Particle Operation

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<box> {
            it may only contain particles where {
                it has the action</carrier>.
            }
        }
        create a particle in position<box>.
        create a particle in position<box>::action</carrier>::position<run>.
        create a particle in position<box>::action</carrier>::position<result>::action</worker>::position<run>.
        destroy the particle in position<box>::action</carrier>::position<result>.
        destroy the particle in position<box>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_box = literal.LocalPosition(
            "position<box>",
            constraints=(local.my_domain_com.my_lib.carrier.Carrier,),
            scheduler=self.scheduler,
        )
        self.execution_position_box__action_carrier: (
            local.my_domain_com.my_lib.carrier.CarrierExecution
        )
        self.execution_position_box__action_carrier__position_result__action_worker: (
            local.my_domain_com.my_lib.worker.WorkerExecution
        )
        self.join_for_destroy_position_box = self.scheduler.create_join(2)

    def on_action_parent_occupied(self):
        self.create_position_box()

    def create_position_box(self):
        self.local_position_box.create_particle()
        self.execution_position_box__action_carrier = (
            local.my_domain_com.my_lib.carrier.CarrierExecution(
                self.local_position_box.particle.get_action(
                    local.my_domain_com.my_lib.carrier.Carrier
                ),
                self.scheduler,
            )
        )
        self.execution_position_box__action_carrier.join_when_empty_position_result = literal.NO_JOIN
        self.execution_position_box__action_carrier.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_box__action_carrier.join_for_move_position_source_to_position_result = literal.NO_JOIN
        self.execution_position_box__action_carrier.join_for_destroy_position_run = literal.NO_JOIN
        self.execution_position_box__action_carrier.guarantees.position_source__move__position_result.inits.append(
            self.init_position_box__action_carrier__position_source__move__position_result
        )
        self.execution_position_box__action_carrier.guarantees.position_source__move__position_result.consumers.append(
            self.create_position_box__action_carrier__position_result__action_worker__position_run
        )
        self.execution_position_box__action_carrier.guarantees.position_run.consumers.append(
            self.destroy_position_box
        )
        self.scheduler.submit(
            self.create_position_box__action_carrier__position_run
        )
        self.execution_position_box__action_carrier.accept_when_empty_position_source()

    def init_position_box__action_carrier__position_source__move__position_result(self):
        self.execution_position_box__action_carrier__position_result__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.local_position_box.particle.get_action(
                    local.my_domain_com.my_lib.carrier.Carrier
                ).get_interface_position(
                    "position<result>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_box__action_carrier__position_result__action_worker.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_box__action_carrier__position_result__action_worker.join_for_destroy_position_run = literal.NO_JOIN
        self.execution_position_box__action_carrier__position_result__action_worker.guarantees.position_run.consumers.append(
            self.destroy_position_box__action_carrier__position_result
        )

    def destroy_position_box__action_carrier__position_result(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.carrier.Carrier
        ).get_interface_position(
            "position<result>"
        ).destroy_particle()
        self.destroy_position_box()

    def destroy_position_box(self):
        if not self.join_for_destroy_position_box.arrive():
            return
        self.local_position_box.destroy_particle()

    def create_position_box__action_carrier__position_run(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.carrier.Carrier
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_box__action_carrier.accept_for_empty_rule_position_run()

    def create_position_box__action_carrier__position_result__action_worker__position_run(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.carrier.Carrier
        ).get_interface_position(
            "position<result>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_box__action_carrier__position_result__action_worker.accept_for_empty_rule_position_run()
```

Source (`carrier.dfn`):

```define
define the potential action<my.domain.com:my_lib:/carrier> {
    define the position<source> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    define the position<result> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<source>.
        move the particle in position<source> to position<result>.
        destroy the particle in position<run>.
    }
}
```

Expected generated `carrier/__init__.py`:

```python
@final
class CarrierGuarantees:
    def __init__(self):
        self.position_source__move__position_result = (
            literal.Guarantee()
        )
        self.position_run = literal.Guarantee()


@final
class CarrierExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = CarrierGuarantees()
        self.destruction_connections = destruction_connections
        self.join_for_move_position_source_to_position_result: literal.Join
        self.join_for_destroy_position_run: literal.Join
        self.join_when_empty_position_result: literal.Join
        self.join_for_empty_rule_position_run: literal.Join

    def accept_when_empty_position_source(self):
        self.create_position_source()

    def accept_when_empty_position_result(self):
        if not self.join_when_empty_position_result.arrive():
            return
        self.move_position_source_to_position_result()

    def accept_for_empty_rule_position_run(self):
        if not self.join_for_empty_rule_position_run.arrive():
            return
        self.destroy_position_run()

    def create_position_source(self):
        self.action.get_interface_position(
            "position<source>"
        ).create_particle()
        self.move_position_source_to_position_result()

    def move_position_source_to_position_result(self):
        if not self.join_for_move_position_source_to_position_result.arrive():
            return
        self.action.get_interface_position("position<source>").move_particle_to(
            self.action.get_interface_position(
                "position<result>"
            )
        )
        self.guarantees.position_source__move__position_result.publish(
            self.scheduler
        )

    def destroy_position_run(self):
        if not self.join_for_destroy_position_run.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_run)

    def continue_destroy_position_run(self):
        self.action.get_interface_position("position<run>").destroy_particle()
        self.guarantees.position_run.publish(self.scheduler)
```

Source (`worker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        destroy the particle in position<run>.
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_run = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.destruction_connections = destruction_connections
        self.join_for_destroy_position_run: literal.Join
        self.join_for_empty_rule_position_run: literal.Join

    def accept_for_empty_rule_position_run(self):
        if not self.join_for_empty_rule_position_run.arrive():
            return
        self.destroy_position_run()

    def destroy_position_run(self):
        if not self.join_for_destroy_position_run.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_run)

    def continue_destroy_position_run(self):
        self.action.get_interface_position("position<run>").destroy_particle()
        self.guarantees.position_run.publish(self.scheduler)
```

## Caller work before a callee Binding Hole

Supporting Position definition (`a.dfn`):

```define
define the potential position<my.domain.com:my_lib:/a>.
```

Supporting Position definition (`target.dfn`):

```define
define the potential position<my.domain.com:my_lib:/target>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it also assigns the action</triggered>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</a>.
            }
        }
        create a particle in position<source>.
        create a particle in position<source>::position</a>.
        move the particle in position<source> to action</triggered>::position<run>.
    }
}
```

Expected generated `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(self, scheduler)
        execution.join_when_empty_global_position_target = literal.NO_JOIN
        execution.join_for_action_triggered__for_empty_rule_position_run = (
            scheduler.create_join(2)
        )
        scheduler.submit(execution.on_action_parent_occupied)
        execution.accept_when_empty_global_position_target()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.local_position_source = literal.LocalPosition(
            "position<source>",
            constraints=(local.my_domain_com.my_lib.a.A,),
            scheduler=self.scheduler,
        )
        self.destruction_connection_action_triggered = (
            literal.DestructionConnection(
                self.scheduler,
                1,
                self.destroy_action_triggered__position_run__global_position_a,
            )
        )
        self.execution_action_triggered = (
            local.my_domain_com.my_lib.triggered.TriggeredExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.triggered.Triggered
                ),
                self.scheduler,
                destruction_connections=literal.DestructionConnections(
                    {
                        local.my_domain_com.my_lib.triggered.TriggeredExecution.continue_destroy_global_position_target: self.destruction_connection_action_triggered,
                    }
                ),
            )
        )
        self.execution_action_triggered.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_action_triggered.join_for_move_position_run_to_global_position_target = literal.NO_JOIN
        self.join_when_empty_global_position_target: literal.Join
        self.join_for_action_triggered__for_empty_rule_position_run: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_source()

    def accept_when_empty_global_position_target(self):
        if not self.join_when_empty_global_position_target.arrive():
            return
        self.action_triggered__for_empty_rule_position_run()

    def create_position_source(self):
        self.local_position_source.create_particle()
        self.local_position_source.particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).create_particle()
        self.local_position_source.move_particle_to(
            self.action.on_particle.get_action(
                local.my_domain_com.my_lib.triggered.Triggered
            ).get_interface_position(
                "position<run>"
            )
        )
        self.action_triggered__for_empty_rule_position_run()

    def action_triggered__for_empty_rule_position_run(self):
        if not self.join_for_action_triggered__for_empty_rule_position_run.arrive():
            return
        # /test must retain this Position before /triggered moves its parent.
        self.destruction_position_action_triggered__position_run__global_position_a = self.action.on_particle.get_action(
            local.my_domain_com.my_lib.triggered.Triggered
        ).get_interface_position(
            "position<run>"
        ).particle.get_position(
            local.my_domain_com.my_lib.a.A
        )
        self.execution_action_triggered.accept_for_empty_rule_position_run()

    def destroy_action_triggered__position_run__global_position_a(self):
        self.destruction_position_action_triggered__position_run__global_position_a.destroy_particle()
        self.destruction_connection_action_triggered.complete()
```

Source (`triggered.dfn`):

```define
define the potential action<my.domain.com:my_lib:/triggered> {
    it also assigns the position</target>.
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        move the particle in position<run> to position</target>.
        destroy the particle in position</target>.
    }
}
```

Expected generated `triggered/__init__.py`:

```python
@final
class TriggeredGuarantees:
    def __init__(self):
        self.position_run = literal.Guarantee()
        self.global_position_target = literal.Guarantee()


@final
class TriggeredExecution:
    def __init__(
        self,
        action,
        scheduler,
        *,
        destruction_connections=None,
    ):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = TriggeredGuarantees()
        self.destruction_connections = destruction_connections
        self.join_for_move_position_run_to_global_position_target: literal.Join
        self.join_for_empty_rule_position_run: literal.Join

    def accept_for_empty_rule_position_run(self):
        if not self.join_for_empty_rule_position_run.arrive():
            return
        self.move_position_run_to_global_position_target()

    def move_position_run_to_global_position_target(self):
        if not self.join_for_move_position_run_to_global_position_target.arrive():
            return
        self.action.get_interface_position(
            "position<run>"
        ).move_particle_to(
            self.action.on_particle.get_position(
                local.my_domain_com.my_lib.target.Target
            )
        )
        self.guarantees.position_run.publish(
            self.scheduler,
            self.destroy_global_position_target,
        )

    def destroy_global_position_target(self):
        literal.continue_destruction(
            self.continue_destroy_global_position_target
        )

    def continue_destroy_global_position_target(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.target.Target
        ).destroy_particle()
        self.guarantees.global_position_target.publish(self.scheduler)
```

## Destruction Connection created with an Action Execution on a local-position particle

Supporting Position definitions:

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/target>.
```

Supporting Action definition:

```define
define the potential action<my.domain.com:my_lib:/triggered> {
    it also assigns the position</target>.
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        move the particle in position<run> to position</target>.
        destroy the particle in position</target>.
    }
}
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<triggered_parent> {
            it may only contain particles where {
                it has the action</triggered>.
            }
        }
        define the position<source> {
            it may only contain particles where {
                it has the position</a>.
            }
        }
        create a particle in position<triggered_parent>.
        create a particle in position<source>.
        create a particle in position<source>::position</a>.
        move the particle in position<source> to position<triggered_parent>::action</triggered>::position<run>.
    }
}
```

Expected generated `__main__.py` and `test/__init__.py`:

```python
def main():
    literal.start(Test)


class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(scheduler)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(
        self,
        scheduler: literal.Scheduler,
    ):
        self.scheduler = scheduler
        self.local_position_triggered_parent = literal.LocalPosition(
            "position<triggered_parent>",
            constraints=(local.my_domain_com.my_lib.triggered.Triggered,),
            scheduler=self.scheduler,
        )
        self.local_position_source = literal.LocalPosition(
            "position<source>",
            constraints=(local.my_domain_com.my_lib.a.A,),
            scheduler=self.scheduler,
        )
        self.join_for_move_position_source_to_position_triggered_parent__action_triggered__position_run = self.scheduler.create_join(2)

    def on_action_parent_occupied(self):
        self.scheduler.submit(
            self.create_position_triggered_parent
        )
        self.create_position_source()

    def create_position_triggered_parent(self):
        self.local_position_triggered_parent.create_particle()
        self.destruction_connection_position_triggered_parent__action_triggered = literal.DestructionConnection(
            self.scheduler,
            1,
            self.destroy_position_triggered_parent__action_triggered__position_run__global_position_a,
        )
        self.execution_position_triggered_parent__action_triggered = (
            local.my_domain_com.my_lib.triggered.TriggeredExecution(
                self.local_position_triggered_parent.particle.get_action(
                    local.my_domain_com.my_lib.triggered.Triggered
                ),
                self.scheduler,
                destruction_connections=literal.DestructionConnections(
                    {
                        local.my_domain_com.my_lib.triggered.TriggeredExecution.continue_destroy_global_position_target: self.destruction_connection_position_triggered_parent__action_triggered,
                    }
                ),
            )
        )
        self.execution_position_triggered_parent__action_triggered.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_triggered_parent__action_triggered.join_for_move_position_run_to_global_position_target = literal.NO_JOIN
        self.execution_position_triggered_parent__action_triggered.guarantees.position_run.consumers.append(
            self.destroy_position_triggered_parent
        )
        self.move_position_source_to_position_triggered_parent__action_triggered__position_run()

    def create_position_source(self):
        self.local_position_source.create_particle()
        self.local_position_source.particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).create_particle()
        self.move_position_source_to_position_triggered_parent__action_triggered__position_run()

    def move_position_source_to_position_triggered_parent__action_triggered__position_run(self):
        if not self.join_for_move_position_source_to_position_triggered_parent__action_triggered__position_run.arrive():
            return
        self.local_position_source.move_particle_to(
            self.local_position_triggered_parent.particle.get_action(
                local.my_domain_com.my_lib.triggered.Triggered
            ).get_interface_position(
                "position<run>"
            )
        )
        self.destruction_position_position_triggered_parent__action_triggered__position_run__global_position_a = self.local_position_triggered_parent.particle.get_action(
            local.my_domain_com.my_lib.triggered.Triggered
        ).get_interface_position(
            "position<run>"
        ).particle.get_position(
            local.my_domain_com.my_lib.a.A
        )
        self.scheduler.submit(
            self.execution_position_triggered_parent__action_triggered.accept_for_empty_rule_position_run
        )

    def destroy_position_triggered_parent__action_triggered__position_run__global_position_a(self):
        self.destruction_position_position_triggered_parent__action_triggered__position_run__global_position_a.destroy_particle()
        self.destruction_connection_position_triggered_parent__action_triggered.complete()

    def destroy_position_triggered_parent(self):
        self.local_position_triggered_parent.destroy_particle()
```

## Empty Binding Hole available before its Action Execution

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<maker_parent> {
            it may only contain particles where {
                it has the action</maker>.
            }
        }
        create a particle in position<maker_parent>.
        create a particle in position<maker_parent>::action</maker>::position<run>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_maker_parent = literal.LocalPosition(
            "position<maker_parent>",
            constraints=(local.my_domain_com.my_lib.maker.Maker,),
            scheduler=self.scheduler,
        )
        self.execution_position_maker_parent__action_maker: (
            local.my_domain_com.my_lib.maker.MakerExecution
        )
        self.join_for_destroy_position_maker_parent = self.scheduler.create_join(2)

    def on_action_parent_occupied(self):
        self.create_position_maker_parent()

    def create_position_maker_parent(self):
        self.local_position_maker_parent.create_particle()
        self.execution_position_maker_parent__action_maker = (
            local.my_domain_com.my_lib.maker.MakerExecution(
                self.local_position_maker_parent.particle.get_action(
                    local.my_domain_com.my_lib.maker.Maker
                ),
                self.scheduler,
            )
        )
        self.execution_position_maker_parent__action_maker.guarantees.position_result.inits.append(
            self.register_guarantee_position_run
        )
        self.scheduler.submit(
            self.create_position_maker_parent__action_maker__position_run
        )
        self.execution_position_maker_parent__action_maker.accept_when_empty_position_result()

    def create_position_maker_parent__action_maker__position_run(self):
        self.local_position_maker_parent.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.local_position_maker_parent.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<run>"
        ).destroy_particle()
        self.destroy_position_maker_parent()

    def destroy_position_maker_parent__action_maker__position_result(self):
        self.local_position_maker_parent.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<result>"
        ).destroy_particle()
        self.destroy_position_maker_parent()

    def destroy_position_maker_parent(self):
        if not self.join_for_destroy_position_maker_parent.arrive():
            return
        self.local_position_maker_parent.destroy_particle()

    def register_guarantee_position_run(self):
        self.execution_position_maker_parent__action_maker.execution_position_result__action_worker.guarantees.position_run.consumers.append(
            self.destroy_position_maker_parent__action_maker__position_result
        )
```

Source (`maker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/maker> {
    define the position<run>.
    define the position<result> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<result>.
        create a particle in position<result>::action</worker>::position<run>.
    }
}
```

Expected generated `maker/__init__.py`:

```python
@final
class MakerGuarantees:
    def __init__(self):
        self.position_result = literal.Guarantee()


@final
class MakerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MakerGuarantees()
        self.execution_position_result__action_worker: (
            local.my_domain_com.my_lib.worker.WorkerExecution
        )

    def accept_when_empty_position_result(self):
        self.create_position_result()

    def create_position_result(self):
        self.action.get_interface_position(
            "position<result>"
        ).create_particle()
        # Worker's empty local-position Binding Hole is resolved before this
        # Create occupies its Action Parent.
        self.execution_position_result__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.action.get_interface_position(
                    "position<result>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_result__action_worker.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_result__action_worker.join_for_destroy_position_run = literal.NO_JOIN
        self.guarantees.position_result.publish(
            self.scheduler,
            self.create_position_result__action_worker__position_run,
            self.execution_position_result__action_worker.on_action_parent_occupied,
        )

    def create_position_result__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<result>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_result__action_worker.accept_for_empty_rule_position_run()
```

Source (`worker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
        destroy the particle in position<run>.
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_run = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.destruction_connections = destruction_connections
        self.local_position_scratch = literal.LocalPosition(
            "position<scratch>",
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_run: literal.Join
        self.join_for_empty_rule_position_run: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_scratch()

    def accept_for_empty_rule_position_run(self):
        if not self.join_for_empty_rule_position_run.arrive():
            return
        self.destroy_position_run()

    def create_position_scratch(self):
        self.local_position_scratch.create_particle()
        self.local_position_scratch.destroy_particle()

    def destroy_position_run(self):
        if not self.join_for_destroy_position_run.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_run)

    def continue_destroy_position_run(self):
        self.action.get_interface_position("position<run>").destroy_particle()
        self.guarantees.position_run.publish(self.scheduler)
```

## A caller resolves a callee Move to two independent predecessors

Supporting Position definition (`dest.dfn`):

```define
define the potential position<my.domain.com:my_lib:/dest>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it also assigns the action</other>.
    it also assigns the position</dest>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</dest>.
        destroy the particle in position</dest>.
        create a particle in action</other>::position<trigger_pos>.
        destroy the particle in position</dest>.
        destroy the particle in action</other>::position<trigger_pos>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestGuarantees:
    def __init__(self):
        self.global_position_dest = literal.Guarantee()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = TestGuarantees()
        self.execution_action_other = (
            local.my_domain_com.my_lib.other.OtherExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.other.Other
                ),
                self.scheduler,
            )
        )
        self.execution_action_other.join_when_empty_global_position_dest = literal.NO_JOIN
        # The callee's local source Create and the caller's /dest Destroy are
        # independent predecessors of the Move.
        self.execution_action_other.join_for_move_position_src_to_global_position_dest = self.scheduler.create_join(2)
        self.execution_action_other.guarantees.global_position_dest.consumers.append(
            self.destroy_global_position_dest
        )

    def accept_when_empty_global_position_dest(self):
        self.create_global_position_dest()

    def on_action_parent_occupied(self):
        self.scheduler.submit(self.create_action_other__position_trigger_pos)
        self.execution_action_other.on_action_parent_occupied()

    def create_global_position_dest(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.dest.Dest
        ).create_particle()
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.dest.Dest
        ).destroy_particle()
        self.execution_action_other.accept_when_empty_global_position_dest()

    def create_action_other__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()

    def destroy_global_position_dest(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.dest.Dest
        ).destroy_particle()
        self.guarantees.global_position_dest.publish(self.scheduler)
```

Source (`other.dfn`):

```define
define the potential action<my.domain.com:my_lib:/other> {
    it also assigns the position</dest>.
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<src>.
        create a particle in position<src>.
        move the particle in position<src> to position</dest>.
    }
}
```

Expected generated `other/__init__.py`:

```python
@final
class OtherGuarantees:
    def __init__(self):
        self.global_position_dest = literal.Guarantee()


@final
class OtherExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = OtherGuarantees()
        self.local_position_src = literal.LocalPosition(
            "position<src>",
            scheduler=self.scheduler,
        )
        self.join_for_move_position_src_to_global_position_dest: literal.Join
        self.join_when_empty_global_position_dest: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_src()

    def accept_when_empty_global_position_dest(self):
        if not self.join_when_empty_global_position_dest.arrive():
            return
        self.move_position_src_to_global_position_dest()

    def create_position_src(self):
        self.local_position_src.create_particle()
        self.move_position_src_to_global_position_dest()

    def move_position_src_to_global_position_dest(self):
        if not self.join_for_move_position_src_to_global_position_dest.arrive():
            return
        self.local_position_src.move_particle_to(
            self.action.on_particle.get_position(
                local.my_domain_com.my_lib.dest.Dest
            )
        )
        self.guarantees.global_position_dest.publish(self.scheduler)
```

## Repeated Action Executions have execution-scoped Guarantees

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</worker>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker>::position<item>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</worker>::position<item>.
    }
}
```

Expected generated `__main__.py` and `test/__init__.py`:

```python
def main():
    literal.start(Test)


class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(scheduler)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_gateway = literal.LocalPosition(
            "position<gateway>",
            constraints=(local.my_domain_com.my_lib.worker.Worker,),
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_gateway = self.scheduler.create_join(2)

    def on_action_parent_occupied(self):
        self.create_position_gateway()

    def create_position_gateway(self):
        self.local_position_gateway.create_particle()
        # Each invocation gets a distinct Guarantees object so its callbacks
        # cannot be reached by another invocation's Particle Operations.
        self.execution_position_gateway__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.local_position_gateway.particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_worker.join_for_empty_rule_position_item = literal.NO_JOIN
        self.execution_position_gateway__action_worker.join_for_empty_rule_position_trigger_pos = literal.NO_JOIN
        self.execution_position_gateway__action_worker.join_for_move_position_item_to_position_holder = literal.NO_JOIN
        self.execution_position_gateway__action_worker.join_for_destroy_position_trigger_pos = literal.NO_JOIN
        # Only the first invocation's Destroy permits the second trigger Create.
        self.execution_position_gateway__action_worker.guarantees.position_trigger_pos.consumers.append(
            self.create_position_gateway__action_worker__position_trigger_pos_2
        )
        # Only the first invocation's Unchanged Guarantee releases the second
        # invocation's Move.
        self.execution_position_gateway__action_worker.guarantees.position_item.consumers.append(
            self.accept_guarantee_position_gateway__action_worker
        )
        self.execution_position_gateway__action_worker_2 = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.local_position_gateway.particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_worker_2.join_for_empty_rule_position_item = literal.NO_JOIN
        self.execution_position_gateway__action_worker_2.join_for_empty_rule_position_trigger_pos = literal.NO_JOIN
        self.execution_position_gateway__action_worker_2.join_for_move_position_item_to_position_holder = literal.NO_JOIN
        self.execution_position_gateway__action_worker_2.join_for_destroy_position_trigger_pos = literal.NO_JOIN
        self.execution_position_gateway__action_worker_2.guarantees.position_item.consumers.append(
            self.destroy_position_gateway__action_worker__position_item
        )
        self.execution_position_gateway__action_worker_2.guarantees.position_trigger_pos.consumers.append(
            self.destroy_position_gateway
        )
        self.scheduler.submit(
            self.create_position_gateway__action_worker__position_item
        )
        self.create_position_gateway__action_worker__position_trigger_pos()

    def create_position_gateway__action_worker__position_item(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<item>"
        ).create_particle()
        self.execution_position_gateway__action_worker.accept_for_empty_rule_position_item()

    def create_position_gateway__action_worker__position_trigger_pos(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.execution_position_gateway__action_worker.accept_for_empty_rule_position_trigger_pos()

    def create_position_gateway__action_worker__position_trigger_pos_2(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.execution_position_gateway__action_worker_2.accept_for_empty_rule_position_trigger_pos()

    def destroy_position_gateway__action_worker__position_item(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<item>"
        ).destroy_particle()
        self.destroy_position_gateway()

    def destroy_position_gateway(self):
        if not self.join_for_destroy_position_gateway.arrive():
            return
        self.local_position_gateway.destroy_particle()

    def accept_guarantee_position_gateway__action_worker(self):
        self.execution_position_gateway__action_worker_2.accept_for_empty_rule_position_item()
```

Source (`worker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<trigger_pos>.
    define the position<item>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<holder>.
        move the particle in position<item> to position<holder>.
        move the particle in position<holder> to position<item>.
        destroy the particle in position<trigger_pos>.
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_item = literal.Guarantee()
        self.position_trigger_pos = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.destruction_connections = destruction_connections
        self.local_position_holder = literal.LocalPosition(
            "position<holder>",
            scheduler=self.scheduler,
        )
        self.join_for_move_position_item_to_position_holder: literal.Join
        self.join_for_destroy_position_trigger_pos: literal.Join
        self.join_for_empty_rule_position_item: literal.Join
        self.join_for_empty_rule_position_trigger_pos: literal.Join

    def accept_for_empty_rule_position_item(self):
        if not self.join_for_empty_rule_position_item.arrive():
            return
        self.move_position_item_to_position_holder()

    def accept_for_empty_rule_position_trigger_pos(self):
        if not self.join_for_empty_rule_position_trigger_pos.arrive():
            return
        self.destroy_position_trigger_pos()

    def move_position_item_to_position_holder(self):
        if not self.join_for_move_position_item_to_position_holder.arrive():
            return
        self.action.get_interface_position(
            "position<item>"
        ).move_particle_to(self.local_position_holder)
        self.local_position_holder.move_particle_to(
            self.action.get_interface_position("position<item>")
        )
        self.guarantees.position_item.publish(
            self.scheduler
        )

    def destroy_position_trigger_pos(self):
        if not self.join_for_destroy_position_trigger_pos.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_trigger_pos)

    def continue_destroy_position_trigger_pos(self):
        self.action.get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        self.guarantees.position_trigger_pos.publish(
            self.scheduler
        )
```

## A joined Particle Operation initializes an ordinary Action Execution

Supporting Position definitions:

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/b>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</other>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
        destroy the particle in position<gateway>::action</other>::position<dest>.
        destroy the particle in position<gateway>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_gateway = literal.LocalPosition(
            "position<gateway>",
            constraints=(local.my_domain_com.my_lib.other.Other,),
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_gateway__action_other__position_dest = self.scheduler.create_join(3)
        self.join_for_destroy_position_gateway = self.scheduler.create_join(2)

    def create_position_gateway(self):
        self.local_position_gateway.create_particle()
        self.execution_position_gateway__action_other = (
            local.my_domain_com.my_lib.other.OtherExecution(
                self.local_position_gateway.particle.get_action(
                    local.my_domain_com.my_lib.other.Other
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_other.join_when_empty_position_dest = literal.NO_JOIN
        self.execution_position_gateway__action_other.join_for_empty_rule_position_trigger_pos = literal.NO_JOIN
        self.execution_position_gateway__action_other.join_for_move_position_src_to_position_dest = self.scheduler.create_join(2)
        self.execution_position_gateway__action_other.join_for_destroy_position_trigger_pos = literal.NO_JOIN
        self.execution_position_gateway__action_other.guarantees.position_src__move__position_dest.consumers.append(
            self.destroy_position_gateway__action_other__position_dest__global_position_b
        )
        self.execution_position_gateway__action_other.guarantees.position_src__move__position_dest.consumers.append(
            self.destroy_position_gateway__action_other__position_dest__global_position_a
        )
        self.execution_position_gateway__action_other.guarantees.position_trigger_pos.consumers.append(
            self.destroy_position_gateway
        )
        self.execution_position_gateway__action_other.guarantees.position_src__move__position_dest.inits.append(
            self.register_guarantee_position_run
        )
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_trigger_pos
        )
        self.execution_position_gateway__action_other.accept_when_empty_position_src()

    def create_position_gateway__action_other__position_trigger_pos(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.execution_position_gateway__action_other.accept_for_empty_rule_position_trigger_pos()

    def destroy_position_gateway__action_other__position_dest__global_position_b(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).particle.get_position(
            local.my_domain_com.my_lib.b.B
        ).destroy_particle()
        self.destroy_position_gateway__action_other__position_dest()

    def destroy_position_gateway__action_other__position_dest__global_position_a(self):
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).destroy_particle()
        self.destroy_position_gateway__action_other__position_dest()

    def register_guarantee_position_run(self):
        self.execution_position_gateway__action_other.execution_position_dest__action_worker.guarantees.position_run.consumers.append(
            self.destroy_position_gateway__action_other__position_dest
        )

    def destroy_position_gateway__action_other__position_dest(self):
        if not self.join_for_destroy_position_gateway__action_other__position_dest.arrive():
            return
        self.local_position_gateway.particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).destroy_particle()
        self.destroy_position_gateway()

    def destroy_position_gateway(self):
        if not self.join_for_destroy_position_gateway.arrive():
            return
        self.local_position_gateway.destroy_particle()
```

Source (`other.dfn`):

```define
define the potential action<my.domain.com:my_lib:/other> {
    define the position<trigger_pos>.
    define the position<dest> {
        it may only contain particles where {
            it has the position</a>.
            it has the position</b>.
            it has the action</worker>.
        }
    }
    define the position<src> {
        it may only contain particles where {
            it has the position</a>.
            it has the position</b>.
            it has the action</worker>.
        }
    }
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        create a particle in position<src>.
        create a particle in position<src>::position</a>.
        create a particle in position<src>::position</b>.
        move the particle in position<src> to position<dest>.
        create a particle in position<dest>::action</worker>::position<run>.
        destroy the particle in position<trigger_pos>.
    }
}
```

Expected generated `other/__init__.py`:

```python
@final
class OtherGuarantees:
    def __init__(self):
        self.position_src__move__position_dest = literal.Guarantee()
        self.position_trigger_pos = literal.Guarantee()


@final
class OtherExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = OtherGuarantees()
        self.destruction_connections = destruction_connections
        self.execution_position_dest__action_worker: (
            local.my_domain_com.my_lib.worker.WorkerExecution
        )
        self.join_for_move_position_src_to_position_dest: literal.Join
        self.join_for_destroy_position_trigger_pos: literal.Join
        self.join_when_empty_position_dest: literal.Join
        self.join_for_empty_rule_position_trigger_pos: literal.Join

    def accept_when_empty_position_src(self):
        self.create_position_src()

    def accept_when_empty_position_dest(self):
        if not self.join_when_empty_position_dest.arrive():
            return
        self.move_position_src_to_position_dest()

    def accept_for_empty_rule_position_trigger_pos(self):
        if not self.join_for_empty_rule_position_trigger_pos.arrive():
            return
        self.destroy_position_trigger_pos()

    def create_position_src(self):
        self.action.get_interface_position("position<src>").create_particle()
        self.scheduler.submit(self.create_position_src__global_position_a)
        self.create_position_src__global_position_b()

    def create_position_src__global_position_a(self):
        self.action.get_interface_position(
            "position<src>"
        ).particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).create_particle()
        self.move_position_src_to_position_dest()

    def create_position_src__global_position_b(self):
        self.action.get_interface_position(
            "position<src>"
        ).particle.get_position(
            local.my_domain_com.my_lib.b.B
        ).create_particle()
        self.move_position_src_to_position_dest()

    def move_position_src_to_position_dest(self):
        if not self.join_for_move_position_src_to_position_dest.arrive():
            return
        self.action.get_interface_position("position<src>").move_particle_to(
            self.action.get_interface_position("position<dest>")
        )
        # Only the final join arrival performs the Move and inits the
        # Action Execution whose Action Parent is the Move target.
        self.execution_position_dest__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.action.get_interface_position(
                    "position<dest>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_dest__action_worker.join_for_empty_rule_position_run = literal.NO_JOIN
        self.execution_position_dest__action_worker.join_for_destroy_position_run = literal.NO_JOIN
        self.guarantees.position_src__move__position_dest.publish(
            self.scheduler,
            self.create_position_dest__action_worker__position_run,
            self.execution_position_dest__action_worker.on_action_parent_occupied,
        )

    def create_position_dest__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<dest>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_dest__action_worker.accept_for_empty_rule_position_run()

    def destroy_position_trigger_pos(self):
        if not self.join_for_destroy_position_trigger_pos.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_trigger_pos)

    def continue_destroy_position_trigger_pos(self):
        self.action.get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        self.guarantees.position_trigger_pos.publish(self.scheduler)
```

Source (`worker.dfn`):

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<scratch>.
        create a particle in position<scratch>.
        destroy the particle in position<scratch>.
        destroy the particle in position<run>.
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_run = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.destruction_connections = destruction_connections
        self.local_position_scratch = literal.LocalPosition(
            "position<scratch>",
            scheduler=self.scheduler,
        )
        self.join_for_destroy_position_run: literal.Join
        self.join_for_empty_rule_position_run: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_scratch()

    def accept_for_empty_rule_position_run(self):
        if not self.join_for_empty_rule_position_run.arrive():
            return
        self.destroy_position_run()

    def create_position_scratch(self):
        self.local_position_scratch.create_particle()
        self.local_position_scratch.destroy_particle()

    def destroy_position_run(self):
        if not self.join_for_destroy_position_run.arrive():
            return
        literal.continue_destruction(self.continue_destroy_position_run)

    def continue_destroy_position_run(self):
        self.action.get_interface_position("position<run>").destroy_particle()
        self.guarantees.position_run.publish(self.scheduler)
```

## A Destructor Binding Hole fans out without serializing its Destroy

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<box> {
            it may only contain particles where {
                it has the action</destructor>.
            }
        }
        create a particle in position<box>.
        destroy the particle in position<box>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_box = literal.LocalPosition(
            "position<box>",
            constraints=(local.my_domain_com.my_lib.destructor.Destructor,),
            scheduler=self.scheduler,
        )

    def create_position_box(self):
        self.local_position_box.create_particle()
        self.execution_position_box__action_destructor = (
            local.my_domain_com.my_lib.destructor.DestructorExecution(
                self.scheduler,
            )
        )
        # The Destroy and both operations released by the Destructor's Action
        # Parent Binding Hole depend on this Create, not on one another.
        self.scheduler.submit(self.destroy_position_box)
        self.execution_position_box__action_destructor.on_action_parent_occupied()

    def destroy_position_box(self):
        self.local_position_box.destroy_particle()
```

Source (`destructor.dfn`):

```define
define the potential action<my.domain.com:my_lib:/destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<first>.
        define the position<second>.
        create a particle in position<first>.
        destroy the particle in position<first>.
        create a particle in position<second>.
        destroy the particle in position<second>.
    }
}
```

Expected generated `destructor/__init__.py`:

```python
class Destructor(literal.Action):
    pass


@final
class DestructorExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_first = literal.LocalPosition(
            "position<first>",
            scheduler=self.scheduler,
        )
        self.local_position_second = literal.LocalPosition(
            "position<second>",
            scheduler=self.scheduler,
        )

    def on_action_parent_occupied(self):
        # The Action Parent Binding Hole is each fragment's complete predecessor
        # set, so the fanout invokes them directly without fragment joins.
        self.scheduler.submit(self.create_position_first)
        self.create_position_second()

    def create_position_first(self):
        self.local_position_first.create_particle()
        self.local_position_first.destroy_particle()

    def create_position_second(self):
        self.local_position_second.create_particle()
        self.local_position_second.destroy_particle()
```

## One Move fans out to two child Destroys

Supporting Position definitions:

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/b>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</a>.
                it has the position</b>.
            }
        }
        define the position<destination>.
        create a particle in position<source>.
        create a particle in position<source>::position</a>.
        create a particle in position<source>::position</b>.
        move the particle in position<source> to position<destination>.
        destroy the particle in position<destination>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.local_position_source = literal.LocalPosition(
            "position<source>",
            constraints=(
                local.my_domain_com.my_lib.a.A,
                local.my_domain_com.my_lib.b.B,
            ),
            scheduler=self.scheduler,
        )
        self.local_position_destination = literal.LocalPosition(
            "position<destination>",
            scheduler=self.scheduler,
        )
        self.join_for_move_position_source_to_position_destination = (
            self.scheduler.create_join(2)
        )
        self.join_for_destroy_position_destination = self.scheduler.create_join(2)

    def create_position_source(self):
        self.local_position_source.create_particle()
        self.scheduler.submit(self.create_position_source__global_position_a)
        self.create_position_source__global_position_b()

    def create_position_source__global_position_a(self):
        self.local_position_source.particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).create_particle()
        self.move_position_source_to_position_destination()

    def create_position_source__global_position_b(self):
        self.local_position_source.particle.get_position(
            local.my_domain_com.my_lib.b.B
        ).create_particle()
        self.move_position_source_to_position_destination()

    def move_position_source_to_position_destination(self):
        if not self.join_for_move_position_source_to_position_destination.arrive():
            return
        self.local_position_source.move_particle_to(self.local_position_destination)
        # Both child Destroys depend directly on this Move, so their fragment
        # methods are released concurrently.
        self.scheduler.submit(self.destroy_position_destination__global_position_b)
        self.destroy_position_destination__global_position_a()

    def destroy_position_destination__global_position_a(self):
        self.local_position_destination.particle.get_position(
            local.my_domain_com.my_lib.a.A
        ).destroy_particle()
        self.destroy_position_destination()

    def destroy_position_destination__global_position_b(self):
        self.local_position_destination.particle.get_position(
            local.my_domain_com.my_lib.b.B
        ).destroy_particle()
        self.destroy_position_destination()

    def destroy_position_destination(self):
        if not self.join_for_destroy_position_destination.arrive():
            return
        self.local_position_destination.destroy_particle()
```

## A later caller contributes multiple Particle Operations to an Empty Rule

Supporting Position definitions:

```define
define the potential position<my.domain.com:my_lib:/input> {
    it may only contain particles where {
        it has the position</first>.
        it has the position</second>.
        it has the position</third>.
    }
}

define the potential position<my.domain.com:my_lib:/first>.
define the potential position<my.domain.com:my_lib:/second>.
define the potential position<my.domain.com:my_lib:/third>.
```

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    it also assigns the position</input>.
    it also assigns the action</middle_action>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<second_holder>.
        define the position<third_holder>.
        create a particle in position</input>.
        create a particle in position</input>::position</second>.
        move the particle in position</input>::position</second> to position<second_holder>.
        destroy the particle in position<second_holder>.
        create a particle in position</input>::position</third>.
        move the particle in position</input>::position</third> to position<third_holder>.
        destroy the particle in position<third_holder>.
        create a particle in action</middle_action>::position<trigger_pos>.
        destroy the particle in action</middle_action>::position<trigger_pos>.
    }
}
```

Expected generated `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    @override
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(self, scheduler)
        scheduler.submit(execution.accept_when_empty_global_position_input)
        execution.on_action_parent_occupied()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.local_position_second_holder = literal.LocalPosition(
            "position<second_holder>",
            scheduler=self.scheduler,
        )
        self.local_position_third_holder = literal.LocalPosition(
            "position<third_holder>",
            scheduler=self.scheduler,
        )
        self.execution_action_middle_action = (
            local.my_domain_com.my_lib.middle_action.MiddleActionExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.middle_action.MiddleAction
                ),
                self.scheduler,
            )
        )
        # The two independent caller child Moves resolve MiddleAction's
        # propagated Empty Rule Binding Hole.
        self.execution_action_middle_action.join_for_empty_rule_global_position_input = self.scheduler.create_join(2)
        self.execution_action_middle_action.join_for_action_inner__for_empty_rule_global_position_input = self.scheduler.create_join(2)

    def accept_when_empty_global_position_input(self):
        self.create_global_position_input()

    def on_action_parent_occupied(self):
        self.scheduler.submit(
            self.create_action_middle_action__position_trigger_pos
        )
        self.execution_action_middle_action.on_action_parent_occupied()

    def create_global_position_input(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).create_particle()
        self.scheduler.submit(
            self.create_global_position_input__global_position_second
        )
        self.scheduler.submit(
            self.create_global_position_input__global_position_third
        )
        self.execution_action_middle_action.accept_when_empty_global_position_input__global_position_first()

    def create_global_position_input__global_position_second(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.second.Second
        ).create_particle()
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.second.Second
        ).move_particle_to(self.local_position_second_holder)
        self.scheduler.submit(self.destroy_position_second_holder)
        self.execution_action_middle_action.accept_for_empty_rule_global_position_input()

    def destroy_position_second_holder(self):
        self.local_position_second_holder.destroy_particle()

    def create_global_position_input__global_position_third(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.third.Third
        ).create_particle()
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.third.Third
        ).move_particle_to(self.local_position_third_holder)
        self.scheduler.submit(self.destroy_position_third_holder)
        self.execution_action_middle_action.accept_for_empty_rule_global_position_input()

    def destroy_position_third_holder(self):
        self.local_position_third_holder.destroy_particle()

    def create_action_middle_action__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.middle_action.MiddleAction
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.middle_action.MiddleAction
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
```

Source (`middle_action.dfn`):

```define
define the potential action<my.domain.com:my_lib:/middle_action> {
    it also assigns the position</input>.
    it also assigns the action</inner>.
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        create a particle in position</input>::position</first>.
        create a particle in action</inner>::position<trigger_pos>.
        destroy the particle in action</inner>::position<trigger_pos>.
    }
}
```

Expected generated `middle_action/__init__.py`:

```python
@final
class MiddleActionExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.destruction_connections = destruction_connections
        self.join_for_empty_rule_global_position_input: literal.Join
        self.join_for_action_inner__for_empty_rule_global_position_input: literal.Join
        self.destruction_connection_action_inner = literal.DestructionConnection(
            self.scheduler,
            1,
            self.destroy_global_position_input__global_position_first,
            forwarded_connection=(
                self.destruction_connections.connection(
                    local.my_domain_com.my_lib.inner.InnerExecution.continue_destroy_position_holder
                )
                if self.destruction_connections is not None
                else None
            ),
        )
        self.execution_action_inner = (
            local.my_domain_com.my_lib.inner.InnerExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.inner.Inner
                ),
                self.scheduler,
                destruction_connections=literal.DestructionConnections(
                    {
                        local.my_domain_com.my_lib.inner.InnerExecution.continue_destroy_position_holder: self.destruction_connection_action_inner,
                    },
                    forwarded=self.destruction_connections,
                ),
            )
        )
        self.execution_action_inner.join_for_empty_rule_global_position_input = literal.NO_JOIN
        self.execution_action_inner.join_for_move_global_position_input_to_position_holder = literal.NO_JOIN

    def accept_when_empty_global_position_input__global_position_first(self):
        self.create_global_position_input__global_position_first()

    def on_action_parent_occupied(self):
        self.create_action_inner__position_trigger_pos()

    def accept_for_empty_rule_global_position_input(self):
        if not self.join_for_empty_rule_global_position_input.arrive():
            return
        self.action_inner__for_empty_rule_global_position_input()

    def create_global_position_input__global_position_first(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.first.First
        ).create_particle()
        self.action_inner__for_empty_rule_global_position_input()

    def create_action_inner__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.inner.Inner
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.inner.Inner
        ).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()

    def action_inner__for_empty_rule_global_position_input(self):
        if not self.join_for_action_inner__for_empty_rule_global_position_input.arrive():
            return
        self.destruction_position_global_position_input__global_position_first = self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).particle.get_position(
            local.my_domain_com.my_lib.first.First
        )
        self.execution_action_inner.accept_for_empty_rule_global_position_input()

    def destroy_global_position_input__global_position_first(self):
        literal.continue_destruction(
            self.continue_destroy_global_position_input__global_position_first
        )

    def continue_destroy_global_position_input__global_position_first(self):
        self.destruction_position_global_position_input__global_position_first.destroy_particle()
        self.destruction_connection_action_inner.complete()
```

Source (`inner.dfn`):

```define
define the potential action<my.domain.com:my_lib:/inner> {
    it also assigns the position</input>.
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<holder>.
        move the particle in position</input> to position<holder>.
        destroy the particle in position<holder>.
    }
}
```

Expected generated `inner/__init__.py`:

```python
@final
class InnerGuarantees:
    def __init__(self):
        self.global_position_input = literal.Guarantee()


@final
class InnerExecution:
    def __init__(self, action, scheduler, *, destruction_connections=None):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = InnerGuarantees()
        self.destruction_connections = destruction_connections
        self.local_position_holder = literal.LocalPosition(
            "position<holder>",
            scheduler=self.scheduler,
        )
        self.join_for_empty_rule_global_position_input: literal.Join
        self.join_for_move_global_position_input_to_position_holder: literal.Join

    def accept_for_empty_rule_global_position_input(self):
        if not self.join_for_empty_rule_global_position_input.arrive():
            return
        self.move_global_position_input_to_position_holder()

    def move_global_position_input_to_position_holder(self):
        if not self.join_for_move_global_position_input_to_position_holder.arrive():
            return
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.input.Input
        ).move_particle_to(self.local_position_holder)
        self.guarantees.global_position_input.publish(
            self.scheduler,
            self.destroy_position_holder,
        )

    def destroy_position_holder(self):
        literal.continue_destruction(self.continue_destroy_position_holder)

    def continue_destroy_position_holder(self):
        self.local_position_holder.destroy_particle()
```
