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
        create a particle in action</runner>::position<wrapper>.
        create a particle in action</runner>::position<independent_parent>.
        create a particle in action</runner>::position<run>.
    }
}
```

Expected `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(
            self,
            scheduler,
        )
        execution.scheduler.submit(
            execution.create_action_runner__position_wrapper
        )
        execution.scheduler.submit(
            execution.create_action_runner__position_independent_parent
        )
        execution.create_action_runner__position_run()


@final
class TestExecution:
    def __init__(
        self,
        action: Test,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.execution_action_runner = (
            local.my_domain_com.my_lib.runner.RunnerExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.runner.Runner
                ),
                self.scheduler,
            )
        )

    def create_action_runner__position_wrapper(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<wrapper>"
        ).create_particle()

        # The Create makes Middle's Action Parent available, so Test initializes
        # that propagated Action Execution before releasing any of its arrivals.
        self.execution_action_runner.init_position_wrapper__action_middle()
        self.execution_action_runner.execution_position_wrapper__action_middle.join_for_move_position_box__action_worker__position_output_to_position_final = literal.NO_JOIN
        self.scheduler.submit(
            self.create_action_runner__position_wrapper__action_middle__position_box
        )
        self.execution_action_runner.accept_when_empty_position_wrapper__action_middle__position_run()

    def create_action_runner__position_wrapper__action_middle__position_box(self):
        # Test owns this caller-specific continuation because it resolves the
        # joins without adding callback setup to Runner or Middle.
        self.execution_action_runner.accept_when_empty_position_wrapper__action_middle__position_box()
        self.execution_action_runner.execution_position_wrapper__action_middle.init_position_box__action_worker()
        self.execution_action_runner.execution_position_wrapper__action_middle.execution_position_box__action_worker.join_for_move_position_input_to_position_output = literal.NO_JOIN
        self.scheduler.submit(
            self.execution_action_runner.execution_position_wrapper__action_middle.accept_when_empty_position_box__action_worker__position_input
        )
        self.execution_action_runner.execution_position_wrapper__action_middle.accept_when_empty_position_box__action_worker__position_run()

    def create_action_runner__position_independent_parent(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<independent_parent>"
        ).create_particle()

        # Independent's Action Parent is propagated through Runner to Test.
        self.execution_action_runner.init_position_independent_parent__action_independent()
        self.scheduler.submit(
            self.execution_action_runner.accept_when_empty_position_independent_parent__action_independent__position_run
        )
        self.execution_action_runner.execution_position_independent_parent__action_independent.on_action_parent_occupied()

    def create_action_runner__position_run(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<run>"
        ).create_particle()
```

Source for `runner/__init__.py` (`runner.dfn`):

```define
define the potential action<my.domain.com:my_lib:/runner> {
    define the position<run>.
    define the position<wrapper> {
        it may only contain particles where {
            it has the action</middle>.
        }
    }
    define the position<independent_parent> {
        it may only contain particles where {
            it has the action</independent>.
        }
    }
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<wrapper>::action</middle>::position<box>.
        create a particle in position<wrapper>::action</middle>::position<run>.
        create a particle in position<independent_parent>::action</independent>::position<run>.
    }
}
```

Expected `runner/__init__.py`:

```python
@final
class RunnerExecution:
    def __init__(
        self,
        action: Runner,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.execution_position_wrapper__action_middle: local.my_domain_com.my_lib.middle.MiddleExecution
        self.execution_position_independent_parent__action_independent: local.my_domain_com.my_lib.independent.IndependentExecution

    # Runner exposes initialization for the propagated Middle Action Execution;
    # the method exists independently of which callers use it.
    def init_position_wrapper__action_middle(self):
        self.execution_position_wrapper__action_middle = (
            local.my_domain_com.my_lib.middle.MiddleExecution(
                self.action.get_interface_position(
                    "position<wrapper>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.middle.Middle
                ),
                self.scheduler,
            )
        )

    def accept_when_empty_position_wrapper__action_middle__position_box(self):
        self.create_position_wrapper__action_middle__position_box()

    def create_position_wrapper__action_middle__position_box(self):
        self.action.get_interface_position(
            "position<wrapper>"
        ).particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<box>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.guarantees.position_box.publish(
            self.scheduler
        )

    def accept_when_empty_position_wrapper__action_middle__position_run(self):
        self.create_position_wrapper__action_middle__position_run()

    def create_position_wrapper__action_middle__position_run(self):
        self.action.get_interface_position(
            "position<wrapper>"
        ).particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.guarantees.position_run.publish(
            self.scheduler
        )

    # Independent's Action Execution and requirements propagate through Runner
    # in the same way as Middle's.
    def init_position_independent_parent__action_independent(self):
        self.execution_position_independent_parent__action_independent = (
            local.my_domain_com.my_lib.independent.IndependentExecution(
                self.action.get_interface_position(
                    "position<independent_parent>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.independent.Independent
                ),
                self.scheduler,
            )
        )

    def accept_when_empty_position_independent_parent__action_independent__position_run(self):
        self.create_position_independent_parent__action_independent__position_run()

    def create_position_independent_parent__action_independent__position_run(self):
        self.action.get_interface_position(
            "position<independent_parent>"
        ).particle.get_action(
            local.my_domain_com.my_lib.independent.Independent
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_independent_parent__action_independent.guarantees.position_run.publish(
            self.scheduler
        )

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
    }
}
```

Expected `middle/__init__.py`:

```python
@final
class MiddleGuarantees:
    def __init__(self):
        self.position_box = literal.Guarantee()
        self.position_run = literal.Guarantee()
        self.position_box__action_worker__position_output__move__position_final = (
            literal.Guarantee()
        )


@final
class MiddleExecution:
    def __init__(
        self,
        action,
        scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MiddleGuarantees()
        self.join_for_move_position_box__action_worker__position_output_to_position_final: literal.Join

    def init_position_box__action_worker(self):
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
        # Middle owns this stable relationship to its direct callee; callers
        # only select the joins used by this particular Action Execution.
        self.execution_position_box__action_worker.guarantees.position_input__move__position_output.consumers.append(
            self.move_position_box__action_worker__position_output_to_position_final
        )

    def accept_when_empty_position_box__action_worker__position_input(self):
        self.create_position_box__action_worker__position_input()

    # This Particle Operation satisfies Worker's propagated input requirement.
    def create_position_box__action_worker__position_input(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<input>"
        ).create_particle()
        self.execution_position_box__action_worker.guarantees.position_input.publish(
            self.scheduler,
            self.execution_position_box__action_worker.accept_when_occupied_position_input,
        )

    def accept_when_empty_position_box__action_worker__position_run(self):
        self.create_position_box__action_worker__position_run()

    # This Particle Operation makes Worker's position<run> occupied.
    def create_position_box__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_box__action_worker.guarantees.position_run.publish(
            self.scheduler
        )

    def accept_when_empty_position_final(self):
        self.move_position_box__action_worker__position_output_to_position_final()

    def move_position_box__action_worker__position_output_to_position_final(self):
        if not self.join_for_move_position_box__action_worker__position_output_to_position_final.arrive():
            return
        self.continue_move_position_box__action_worker__position_output_to_position_final()

    def continue_move_position_box__action_worker__position_output_to_position_final(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<output>"
        ).move_particle_to(
            self.action.get_interface_position("position<final>")
        )
        self.guarantees.position_box__action_worker__position_output__move__position_final.publish(
            self.scheduler
        )
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
    }
}
```

Expected `worker/__init__.py`:

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_input = literal.Guarantee()
        self.position_run = literal.Guarantee()
        self.position_input__move__position_output = (
            literal.Guarantee()
        )


@final
class WorkerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.join_for_move_position_input_to_position_output: literal.Join

    def accept_when_occupied_position_input(self):
        self.move_position_input_to_position_output()

    def accept_when_empty_position_output(self):
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

Expected `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(
            self,
            scheduler,
        )
        execution.create_position_runner_parent()


@final
class TestExecution:
    def __init__(
        self,
        action: Test,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler
        self.local_position_runner_parent = literal.LocalPosition(
            "position<runner_parent>",
            constraints=(local.my_domain_com.my_lib.runner.Runner,),
            scheduler=self.scheduler,
        )

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
        self.execution_position_runner_parent__action_runner.join_for_move_position_first_to_position_first_result = literal.NO_JOIN
        self.execution_position_runner_parent__action_runner.join_for_move_position_second_to_position_second_result = literal.NO_JOIN
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
        self.execution_position_runner_parent__action_runner.accept_when_occupied_position_first()

    def create_position_runner_parent__action_runner__position_second(self):
        self.local_position_runner_parent.particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<second>"
        ).create_particle()
        self.execution_position_runner_parent__action_runner.accept_when_occupied_position_second()
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

    def accept_when_occupied_position_first(self):
        self.move_position_first_to_position_first_result()

    def accept_when_empty_position_first_result(self):
        self.move_position_first_to_position_first_result()

    def accept_when_occupied_position_second(self):
        self.move_position_second_to_position_second_result()

    def accept_when_empty_position_second_result(self):
        self.move_position_second_to_position_second_result()

    def move_position_first_to_position_first_result(self):
        if not self.join_for_move_position_first_to_position_first_result.arrive():
            return
        self.continue_move_position_first_to_position_first_result()

    def continue_move_position_first_to_position_first_result(self):
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
        self.continue_move_position_second_to_position_second_result()

    def continue_move_position_second_to_position_second_result(self):
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
            self.init_position_box__action_maker__position_result__action_destructor
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

    def init_position_box__action_maker__position_result__action_destructor(self):
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
        self.execution_position_box__action_maker__position_result__action_destructor.guarantees.global_position_marker.consumers.append(
            self.destroy_position_box__action_maker__position_result__global_position_marker
        )
        self.execution_position_box__action_maker.guarantees.position_result__global_position_marker.consumers.append(
            self.execution_position_box__action_maker__position_result__action_destructor.accept_when_occupied_global_position_marker
        )

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

    def accept_when_occupied_global_position_marker(self):
        self.move_global_position_marker_to_position_holder()

    def move_global_position_marker_to_position_holder(self):
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
    define the position<gateway> {
        it may only contain particles where {
            it has the action</middle>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</middle>::position<trigger_pos>.
    }
}
```

Expected generated `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    def __init__(self, on_particle: literal.Particle):
        super().__init__(
            on_particle,
            interface_positions=[
                literal.LocalPosition(
                    "position<gateway>",
                    constraints=(local.my_domain_com.my_lib.middle.Middle,),
                    scheduler=on_particle.scheduler,
                ),
            ],
        )

    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(
            self,
            scheduler,
        )
        execution.create_position_gateway()


@final
class TestExecution:
    def __init__(
        self,
        action: Test,
        scheduler: literal.Scheduler,
    ):
        self.action = action
        self.scheduler = scheduler

    def create_position_gateway(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).create_particle()
        self.execution_position_gateway__action_middle = (
            local.my_domain_com.my_lib.middle.MiddleExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
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
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
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
        # Middle owns this fanout because every caller releases the same
        # intrinsic Action Fragments when Middle's Action Parent is occupied.
        self.scheduler.submit(self.create_position_first)
        self.scheduler.submit(self.create_position_second)
        self.scheduler.submit(self.create_action_child_a__position_trigger_pos)
        self.scheduler.submit(self.create_action_child_b__position_trigger_pos)
        self.scheduler.submit(
            self.execution_action_child_a.on_action_parent_occupied
        )
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

    def create_action_child_b__position_trigger_pos(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.child_b.ChildB
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
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
            self.init_position_box__action_maker__position_result__action_destruct_b
        )
        self.execution_position_box__action_maker.guarantees.position_result.inits.append(
            self.init_position_box__action_maker__position_result__action_destruct_a
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

    def init_position_box__action_maker__position_result__action_destruct_b(self):
        self.execution_position_box__action_maker__position_result__action_destruct_b = (
            local.my_domain_com.my_lib.destruct_b.DestructBExecution(
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker.guarantees.position_result.consumers.append(
            self.run_position_box__action_maker__position_result__action_destruct_b
        )

    def init_position_box__action_maker__position_result__action_destruct_a(self):
        self.execution_position_box__action_maker__position_result__action_destruct_a = (
            local.my_domain_com.my_lib.destruct_a.DestructAExecution(
                self.scheduler,
            )
        )
        self.execution_position_box__action_maker.guarantees.position_result.consumers.append(
            self.run_position_box__action_maker__position_result__action_destruct_a
        )

    def run_position_box__action_maker__position_result__action_destruct_b(self):
        self.execution_position_box__action_maker__position_result__action_destruct_b.on_action_parent_occupied()

    def run_position_box__action_maker__position_result__action_destruct_a(self):
        self.execution_position_box__action_maker__position_result__action_destruct_a.on_action_parent_occupied()

    def destroy_position_box__action_maker__position_result(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.maker.Maker
        ).get_interface_position(
            "position<result>"
        ).destroy_particle()
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
        self.scheduler.submit(
            self.create_position_box__action_carrier__position_run
        )
        # Carrier's fragment returns after the Move creates Worker's Action
        # Parent, so Test can configure and release Worker directly.
        self.execution_position_box__action_carrier.on_action_parent_occupied()
        self.execution_position_box__action_carrier__position_result__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.scheduler,
            )
        )
        self.scheduler.submit(
            self.create_position_box__action_carrier__position_result__action_worker__position_run
        )
        self.execution_position_box__action_carrier__position_result__action_worker.on_action_parent_occupied()

    def create_position_box__action_carrier__position_run(self):
        self.local_position_box.particle.get_action(
            local.my_domain_com.my_lib.carrier.Carrier
        ).get_interface_position(
            "position<run>"
        ).create_particle()

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


@final
class CarrierExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = CarrierGuarantees()

    def on_action_parent_occupied(self):
        self.create_position_source()

    def create_position_source(self):
        self.action.get_interface_position(
            "position<source>"
        ).create_particle()
        self.action.get_interface_position(
            "position<source>"
        ).move_particle_to(
            self.action.get_interface_position(
                "position<result>"
            )
        )
        self.guarantees.position_source__move__position_result.publish(
            self.scheduler
        )
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
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerExecution:
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
        # /test must retain this Position before /triggered moves its parent.
        self.destruction_position_action_triggered__position_run__global_position_a = self.action.on_particle.get_action(
            local.my_domain_com.my_lib.triggered.Triggered
        ).get_interface_position(
            "position<run>"
        ).particle.get_position(
            local.my_domain_com.my_lib.a.A
        )
        self.execution_action_triggered.accept_when_occupied_position_run()

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
        self.destruction_connections = destruction_connections

    def accept_when_occupied_position_run(self):
        self.move_position_run_to_global_position_target()

    def move_position_run_to_global_position_target(self):
        self.action.get_interface_position(
            "position<run>"
        ).move_particle_to(
            self.action.on_particle.get_position(
                local.my_domain_com.my_lib.target.Target
            )
        )
        self.destroy_global_position_target()

    def destroy_global_position_target(self):
        literal.continue_destruction(
            self.continue_destroy_global_position_target
        )

    def continue_destroy_global_position_target(self):
        self.action.on_particle.get_position(
            local.my_domain_com.my_lib.target.Target
        ).destroy_particle()
```

## Destruction Connection created with an Action Execution on a local-position particle

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

Expected generated `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(scheduler)
        execution.scheduler.submit(
            execution.create_position_triggered_parent
        )
        execution.create_position_source()


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
        self.execution_position_triggered_parent__action_triggered.accept_when_occupied_position_run()

    def destroy_position_triggered_parent__action_triggered__position_run__global_position_a(self):
        self.destruction_position_position_triggered_parent__action_triggered__position_run__global_position_a.destroy_particle()
        self.destruction_connection_position_triggered_parent__action_triggered.complete()
```

## Empty Binding Hole available before its Action Execution

### `test.dfn`

```define
define the potential action<my.domain.com:my_lib:/test> {
    it also assigns the action</runner>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in action</runner>::position<wrapper>.
        create a particle in action</runner>::position<run>.
    }
}
```

### Generated `test/__init__.py`

```python
class Test(literal.EntryPoint):
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(
            self,
            scheduler,
        )
        execution.scheduler.submit(
            execution.create_action_runner__position_wrapper
        )
        execution.create_action_runner__position_run()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.execution_action_runner = (
            local.my_domain_com.my_lib.runner.RunnerExecution(
                self.action.on_particle.get_action(
                    local.my_domain_com.my_lib.runner.Runner
                ),
                self.scheduler,
            )
        )

    def create_action_runner__position_wrapper(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<wrapper>"
        ).create_particle()
        # Middle's Action Execution and requirements propagated through Runner.
        self.execution_action_runner.init_position_wrapper__action_middle()
        self.execution_action_runner.execution_position_wrapper__action_middle.join_for_move_position_box__action_worker__position_output_to_position_final = literal.NO_JOIN
        self.scheduler.submit(
            self.create_action_runner__position_wrapper__action_middle__position_box
        )
        self.execution_action_runner.accept_when_empty_position_wrapper__action_middle__position_run()

    def create_action_runner__position_wrapper__action_middle__position_box(self):
        # Test owns this caller-specific continuation because it resolves the
        # joins without adding callback setup to Runner or Middle.
        self.execution_action_runner.accept_when_empty_position_wrapper__action_middle__position_box()
        self.execution_action_runner.execution_position_wrapper__action_middle.init_position_box__action_worker()
        self.execution_action_runner.execution_position_wrapper__action_middle.execution_position_box__action_worker.join_for_move_position_input_to_position_output = literal.NO_JOIN
        self.scheduler.submit(
            self.execution_action_runner.execution_position_wrapper__action_middle.accept_when_empty_position_box__action_worker__position_input
        )
        self.execution_action_runner.execution_position_wrapper__action_middle.accept_when_empty_position_box__action_worker__position_run()

    def create_action_runner__position_run(self):
        self.action.on_particle.get_action(
            local.my_domain_com.my_lib.runner.Runner
        ).get_interface_position(
            "position<run>"
        ).create_particle()
```

### `runner.dfn`

```define
define the potential action<my.domain.com:my_lib:/runner> {
    define the position<run>.
    define the position<wrapper> {
        it may only contain particles where {
            it has the action</middle>.
        }
    }
    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<wrapper>::action</middle>::position<box>.
        create a particle in position<wrapper>::action</middle>::position<run>.
    }
}
```

### Generated `runner/__init__.py`

```python
@final
class RunnerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.execution_position_wrapper__action_middle: local.my_domain_com.my_lib.middle.MiddleExecution

    # Middle's Action Execution propagates through Runner, but Runner owns the
    # stable initializer and its code does not depend on Test.
    def init_position_wrapper__action_middle(self):
        self.execution_position_wrapper__action_middle = (
            local.my_domain_com.my_lib.middle.MiddleExecution(
                self.action.get_interface_position(
                    "position<wrapper>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.middle.Middle
                ),
                self.scheduler,
            )
        )

    def accept_when_empty_position_wrapper__action_middle__position_box(self):
        self.create_position_wrapper__action_middle__position_box()

    def create_position_wrapper__action_middle__position_box(self):
        self.action.get_interface_position(
            "position<wrapper>"
        ).particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<box>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.guarantees.position_box.publish(
            self.scheduler
        )

    def accept_when_empty_position_wrapper__action_middle__position_run(self):
        self.create_position_wrapper__action_middle__position_run()

    def create_position_wrapper__action_middle__position_run(self):
        self.action.get_interface_position(
            "position<wrapper>"
        ).particle.get_action(
            local.my_domain_com.my_lib.middle.Middle
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_wrapper__action_middle.guarantees.position_run.publish(
            self.scheduler
        )

```

### `middle.dfn`

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
    }
}
```

### Generated `middle/__init__.py`

```python
@final
class MiddleGuarantees:
    def __init__(self):
        self.position_box = literal.Guarantee()
        self.position_run = literal.Guarantee()
        self.position_box__action_worker__position_output__move__position_final = (
            literal.Guarantee()
        )


@final
class MiddleExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = MiddleGuarantees()
        self.join_for_move_position_box__action_worker__position_output_to_position_final: literal.Join

    def init_position_box__action_worker(self):
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
        # Middle owns this stable relationship to its direct callee; callers
        # only select the joins used by this particular Action Execution.
        self.execution_position_box__action_worker.guarantees.position_input__move__position_output.consumers.append(
            self.move_position_box__action_worker__position_output_to_position_final
        )

    def accept_when_empty_position_box__action_worker__position_input(self):
        self.create_position_box__action_worker__position_input()

    def create_position_box__action_worker__position_input(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<input>"
        ).create_particle()
        self.execution_position_box__action_worker.guarantees.position_input.publish(
            self.scheduler,
            self.execution_position_box__action_worker.accept_when_occupied_position_input,
        )

    def accept_when_empty_position_box__action_worker__position_run(self):
        self.create_position_box__action_worker__position_run()

    def create_position_box__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
        self.execution_position_box__action_worker.guarantees.position_run.publish(
            self.scheduler
        )

    def accept_when_empty_position_final(self):
        self.move_position_box__action_worker__position_output_to_position_final()

    def move_position_box__action_worker__position_output_to_position_final(self):
        if not self.join_for_move_position_box__action_worker__position_output_to_position_final.arrive():
            return
        self.continue_move_position_box__action_worker__position_output_to_position_final()

    def continue_move_position_box__action_worker__position_output_to_position_final(self):
        self.action.get_interface_position(
            "position<box>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<output>"
        ).move_particle_to(
            self.action.get_interface_position("position<final>")
        )
        self.guarantees.position_box__action_worker__position_output__move__position_final.publish(
            self.scheduler
        )
```

### `worker.dfn`

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<run>.
    define the position<input>.
    define the position<output>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        move the particle in position<input> to position<output>.
    }
}
```

### Generated `worker/__init__.py`

```python
@final
class WorkerGuarantees:
    def __init__(self):
        self.position_input = literal.Guarantee()
        self.position_run = literal.Guarantee()
        self.position_input__move__position_output = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.join_for_move_position_input_to_position_output: literal.Join

    def accept_when_occupied_position_input(self):
        self.move_position_input_to_position_output()

    def accept_when_empty_position_output(self):
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

## A caller resolves a callee Move to two independent predecessors

### `test.dfn`

```define
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</other>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</other>::position<dest>.
        destroy the particle in position<gateway>::action</other>::position<dest>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
    }
}
```

### Generated `test/__init__.py`

```python
@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler

    def create_position_gateway(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).create_particle()
        self.execution_position_gateway__action_other = (
            local.my_domain_com.my_lib.other.OtherExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.other.Other
                ),
                self.scheduler,
            )
        )
        # Test's resolved graph has two independent predecessors for Other's
        # Move, so this Action Execution receives a caller-created join.
        self.execution_position_gateway__action_other.join_for_move_position_src_to_position_dest = self.scheduler.create_join(2)
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_dest
        )
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_trigger_pos
        )
        self.execution_position_gateway__action_other.on_action_parent_occupied()

    def create_position_gateway__action_other__position_dest(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).create_particle()
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).destroy_particle()
        # The independent target Empty dependency supplies the second arrival.
        self.execution_position_gateway__action_other.accept_when_empty_position_dest()

    def create_position_gateway__action_other__position_trigger_pos(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
```

### `other.dfn`

```define
define the potential action<my.domain.com:my_lib:/other> {
    define the position<trigger_pos>.
    define the position<dest>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<src>.
        create a particle in position<src>.
        move the particle in position<src> to position<dest>.
    }
}
```

### Generated `other/__init__.py`

```python
@final
class OtherExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.local_position_src = literal.LocalPosition(
            "position<src>",
            scheduler=self.scheduler,
        )
        # Every caller supplies the join implementation without changing Other's
        # generated code.
        self.join_for_move_position_src_to_position_dest: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_src()

    def accept_when_empty_position_dest(self):
        self.move_position_src_to_position_dest()

    def create_position_src(self):
        self.local_position_src.create_particle()
        self.move_position_src_to_position_dest()

    def move_position_src_to_position_dest(self):
        if not self.join_for_move_position_src_to_position_dest.arrive():
            return
        self.continue_move_position_src_to_position_dest()

    def continue_move_position_src_to_position_dest(self):
        self.local_position_src.move_particle_to(
            self.action.get_interface_position(
                "position<dest>"
            )
        )
```

### Alternative `test.dfn`

```define
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</other>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
    }
}
```

### Alternative generated `test/__init__.py`

```python
@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler

    def create_position_gateway(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).create_particle()
        self.execution_position_gateway__action_other = (
            local.my_domain_com.my_lib.other.OtherExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.other.Other
                ),
                self.scheduler,
            )
        )
        # The source Create is this caller's only realized predecessor.
        self.execution_position_gateway__action_other.join_for_move_position_src_to_position_dest = literal.NO_JOIN
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_trigger_pos
        )
        self.execution_position_gateway__action_other.on_action_parent_occupied()

    def create_position_gateway__action_other__position_trigger_pos(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
```

## Repeated Action Executions have execution-scoped Guarantees

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker>::position<item>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
    }
}
```

Expected generated `test/__init__.py`:

```python
class Test(literal.EntryPoint):
    def execute(self, scheduler: literal.Scheduler):
        execution = TestExecution(self, scheduler)
        execution.create_position_gateway()


@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler

    def create_position_gateway(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).create_particle()
        # Each invocation gets a distinct Guarantees object so its callbacks
        # cannot be reached by another invocation's Particle Operations.
        self.execution_position_gateway__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_worker_2 = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.worker.Worker
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_worker.join_for_move_position_item_to_position_holder = literal.NO_JOIN
        self.execution_position_gateway__action_worker_2.join_for_move_position_item_to_position_holder = literal.NO_JOIN
        # Only the first invocation's Unchanged Guarantee releases the second
        # invocation's Move.
        self.execution_position_gateway__action_worker.guarantees.position_holder__move__position_item.consumers.append(
            self.execution_position_gateway__action_worker_2.accept_when_occupied_position_item
        )
        # Only the first invocation's Destroy permits the second trigger Create.
        self.execution_position_gateway__action_worker.guarantees.position_trigger_pos__destroy.consumers.append(
            self.create_position_gateway__action_worker__position_trigger_pos_2
        )
        self.scheduler.submit(
            self.create_position_gateway__action_worker__position_item
        )
        self.create_position_gateway__action_worker__position_trigger_pos()

    def create_position_gateway__action_worker__position_item(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<item>"
        ).create_particle()
        self.execution_position_gateway__action_worker.accept_when_occupied_position_item()

    def create_position_gateway__action_worker__position_trigger_pos(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.execution_position_gateway__action_worker.accept_when_occupied_position_trigger_pos()

    def create_position_gateway__action_worker__position_trigger_pos_2(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.execution_position_gateway__action_worker_2.accept_when_occupied_position_trigger_pos()
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
        self.position_holder__move__position_item = literal.Guarantee()
        self.position_trigger_pos__destroy = literal.Guarantee()


@final
class WorkerExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = WorkerGuarantees()
        self.local_position_holder = literal.LocalPosition(
            "position<holder>",
            scheduler=self.scheduler,
        )
        self.join_for_move_position_item_to_position_holder: literal.Join

    def accept_when_occupied_position_item(self):
        self.move_position_item_to_position_holder()

    def accept_when_empty_position_holder(self):
        self.move_position_item_to_position_holder()

    def accept_when_occupied_position_trigger_pos(self):
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
        self.guarantees.position_holder__move__position_item.publish(
            self.scheduler
        )

    def destroy_position_trigger_pos(self):
        self.action.get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        self.guarantees.position_trigger_pos__destroy.publish(
            self.scheduler
        )
```

## A joined Particle Operation initializes an ordinary Action Execution

Source (`test.dfn`):

```define
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</other>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</other>::position<dest>.
        destroy the particle in position<gateway>::action</other>::position<dest>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
        create a particle in position<gateway>::action</other>::position<dest>::action</worker>::position<run>.
    }
}
```

Expected generated `test/__init__.py`:

```python
@final
class TestExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler

    def create_position_gateway(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).create_particle()
        self.execution_position_gateway__action_other = (
            local.my_domain_com.my_lib.other.OtherExecution(
                self.action.get_interface_position(
                    "position<gateway>"
                ).particle.get_action(
                    local.my_domain_com.my_lib.other.Other
                ),
                self.scheduler,
            )
        )
        self.execution_position_gateway__action_other.join_for_move_position_src_to_position_dest = self.scheduler.create_join(2)
        # Either arrival may reach the join first, so only the Move Guarantee is
        # allowed to initialize and release Worker.
        self.execution_position_gateway__action_other.guarantees.position_src__move__position_dest.inits.append(
            self.init_position_gateway__action_other__position_dest__action_worker
        )
        self.execution_position_gateway__action_other.guarantees.position_src__move__position_dest.consumers.append(
            self.run_position_gateway__action_other__position_dest__action_worker
        )
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_dest
        )
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_trigger_pos
        )
        self.execution_position_gateway__action_other.on_action_parent_occupied()

    def create_position_gateway__action_other__position_dest(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).create_particle()
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).destroy_particle()
        # A non-final arrival returns without performing the Move, so no Worker
        # setup may follow this call directly.
        self.execution_position_gateway__action_other.accept_when_empty_position_dest()

    def create_position_gateway__action_other__position_trigger_pos(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()

    def init_position_gateway__action_other__position_dest__action_worker(self):
        self.execution_position_gateway__action_other__position_dest__action_worker = (
            local.my_domain_com.my_lib.worker.WorkerExecution(
                self.scheduler,
            )
        )

    def run_position_gateway__action_other__position_dest__action_worker(self):
        # These independent operations both follow the Move that supplied
        # Worker's Action Parent from this caller's perspective.
        self.scheduler.submit(
            self.create_position_gateway__action_other__position_dest__action_worker__position_run
        )
        self.execution_position_gateway__action_other__position_dest__action_worker.on_action_parent_occupied()

    def create_position_gateway__action_other__position_dest__action_worker__position_run(self):
        self.action.get_interface_position(
            "position<gateway>"
        ).particle.get_action(
            local.my_domain_com.my_lib.other.Other
        ).get_interface_position(
            "position<dest>"
        ).particle.get_action(
            local.my_domain_com.my_lib.worker.Worker
        ).get_interface_position(
            "position<run>"
        ).create_particle()
```

Source (`other.dfn`):

```define
define the potential action<my.domain.com:my_lib:/other> {
    define the position<trigger_pos>.
    define the position<dest> {
        it may only contain particles where {
            it has the action</worker>.
        }
    }
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<src> {
            it may only contain particles where {
                it has the action</worker>.
            }
        }
        create a particle in position<src>.
        move the particle in position<src> to position<dest>.
    }
}
```

Expected generated `other/__init__.py`:

```python
@final
class OtherGuarantees:
    def __init__(self):
        self.position_src__move__position_dest = literal.Guarantee()


@final
class OtherExecution:
    def __init__(self, action, scheduler):
        self.action = action
        self.scheduler = scheduler
        self.guarantees = OtherGuarantees()
        self.local_position_src = literal.LocalPosition(
            "position<src>",
            constraints=(local.my_domain_com.my_lib.worker.Worker,),
            scheduler=self.scheduler,
        )
        self.join_for_move_position_src_to_position_dest: literal.Join

    def on_action_parent_occupied(self):
        self.create_position_src()

    def accept_when_empty_position_dest(self):
        self.move_position_src_to_position_dest()

    def create_position_src(self):
        self.local_position_src.create_particle()
        # A non-final arrival returns without performing the Move, so no Worker
        # setup may follow this call directly.
        self.move_position_src_to_position_dest()

    def move_position_src_to_position_dest(self):
        if not self.join_for_move_position_src_to_position_dest.arrive():
            return
        self.local_position_src.move_particle_to(
            self.action.get_interface_position(
                "position<dest>"
            )
        )
        # Publication is the only point that proves which arrival actually
        # performed the Move.
        self.guarantees.position_src__move__position_dest.publish(
            self.scheduler
        )
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
    }
}
```

Expected generated `worker/__init__.py`:

```python
@final
class WorkerExecution:
    def __init__(self, scheduler):
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
        # These fragments are independent consumers of the same Binding Hole.
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
        self.scheduler.submit(self.destroy_position_destination__global_position_a)
        self.destroy_position_destination__global_position_b()

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
