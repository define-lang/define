# Generated code examples

## A chain of triggered actions

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        self.on_particle.get_action(Runner).get_interface_position(
            "position<run>"
        ).create_particle()
        self.on_particle.get_action(Runner).run()
        self.on_particle.get_action(Runner).get_interface_position(
            "position<run>"
        ).destroy_particle()
```

### runner.dfn

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

```python
class Runner(literal.Action):
    def run(self):
        wrapper = literal.LocalPosition("position<wrapper>", constraints=(Middle,))
        wrapper.create_particle()
        wrapper.particle.get_action(Middle).get_interface_position(
            "position<box>"
        ).create_particle()
        wrapper.particle.get_action(Middle).get_interface_position(
            "position<run>"
        ).create_particle()
        wrapper.particle.get_action(Middle).run()
        wrapper.particle.get_action(Middle).get_interface_position(
            "position<final>"
        ).destroy_particle()
        wrapper.destroy_particle()
```

### middle.dfn

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

```python
class Middle(literal.Action):
    def run(self):
        self.get_interface_position("position<box>").particle.get_action(
            Worker
        ).get_interface_position("position<input>").create_particle()
        self.get_interface_position("position<box>").particle.get_action(
            Worker
        ).get_interface_position("position<run>").create_particle()
        self.get_interface_position("position<box>").particle.get_action(Worker).run()
        self.get_interface_position("position<box>").particle.get_action(
            Worker
        ).get_interface_position("position<output>").move_particle_to(
            self.get_interface_position("position<final>")
        )
        self.get_interface_position("position<box>").destroy_particle()
        self.get_interface_position("position<run>").destroy_particle()
```

### worker.dfn

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

```python
class Worker(literal.Action):
    def run(self):
        self.get_interface_position("position<input>").move_particle_to(
            self.get_interface_position("position<output>")
        )
        self.get_interface_position("position<run>").destroy_particle()
```

## Actions assigned to particles in local positions

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        runner_parent = literal.LocalPosition(
            "position<runner_parent>", constraints=(Runner,)
        )
        runner_parent.create_particle()
        runner_parent.particle.get_action(Runner).get_interface_position(
            "position<second>"
        ).create_particle()
        runner_parent.particle.get_action(Runner).get_interface_position(
            "position<first>"
        ).create_particle()
        runner_parent.particle.get_action(Runner).run()
        runner_parent.particle.get_action(Runner).get_interface_position(
            "position<second_result>"
        ).destroy_particle()
        runner_parent.particle.get_action(Runner).get_interface_position(
            "position<first_result>"
        ).destroy_particle()
        runner_parent.destroy_particle()
```

### runner.dfn

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

```python
class Runner(literal.Action):
    def run(self):
        self.get_interface_position("position<first>").move_particle_to(
            self.get_interface_position("position<first_result>")
        )
        self.get_interface_position("position<second>").move_particle_to(
            self.get_interface_position("position<second_result>")
        )
```

## A Destructor uses a child initialized by a completed action

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/marker>.
```

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        box = literal.LocalPosition("position<box>", constraints=(Maker,))
        box.create_particle()
        box.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).create_particle()
        box.particle.get_action(Maker).run()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).particle.get_action(Destructor).run()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).particle.get_position(Marker).destroy_particle()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).destroy_particle()
        box.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).destroy_particle()
        box.destroy_particle()
```

### maker.dfn

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

```python
class Maker(literal.Action):
    def run(self):
        self.get_interface_position("position<result>").create_particle()
        self.get_interface_position("position<result>").particle.get_position(
            Marker
        ).create_particle()
```

### destructor.dfn

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

```python
class Destructor(literal.Action):
    def run(self):
        holder = literal.LocalPosition("position<holder>")
        self.on_particle.get_position(Marker).move_particle_to(holder)
        holder.move_particle_to(self.on_particle.get_position(Marker))
```

## Two local operations and two triggered actions

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        gateway = literal.LocalPosition("position<gateway>", constraints=(Middle,))
        gateway.create_particle()
        gateway.particle.get_action(Middle).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        gateway.particle.get_action(Middle).run()
        gateway.particle.get_action(Middle).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        gateway.destroy_particle()
```

### middle.dfn

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

```python
class Middle(literal.Action):
    def run(self):
        first = literal.LocalPosition("position<first>")
        second = literal.LocalPosition("position<second>")
        first.create_particle()
        second.create_particle()
        self.on_particle.get_action(ChildA).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.on_particle.get_action(ChildA).run()
        self.on_particle.get_action(ChildB).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.on_particle.get_action(ChildB).run()
        self.on_particle.get_action(ChildA).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        self.on_particle.get_action(ChildB).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
        first.destroy_particle()
        second.destroy_particle()
```

### child_a.dfn

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

```python
class ChildA(literal.Action):
    def run(self):
        scratch = literal.LocalPosition("position<scratch>")
        scratch.create_particle()
        scratch.destroy_particle()
```

### child_b.dfn

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

```python
class ChildB(literal.Action):
    def run(self):
        scratch = literal.LocalPosition("position<scratch>")
        scratch.create_particle()
        scratch.destroy_particle()
```

## Two Destructors on a callee-created particle

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        box = literal.LocalPosition("position<box>", constraints=(Maker,))
        box.create_particle()
        box.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).create_particle()
        box.particle.get_action(Maker).run()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).particle.get_action(DestructB).run()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).particle.get_action(DestructA).run()
        box.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).destroy_particle()
        box.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).destroy_particle()
        box.destroy_particle()
```

### maker.dfn

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

```python
class Maker(literal.Action):
    def run(self):
        self.get_interface_position("position<result>").create_particle()
```

### destruct_a.dfn

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

```python
class DestructA(literal.Action):
    def run(self):
        _noop = literal.LocalPosition("position<_noop>")
        _noop.create_particle()
        _noop.destroy_particle()
```

### destruct_b.dfn

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

```python
class DestructB(literal.Action):
    def run(self):
        _noop = literal.LocalPosition("position<_noop>")
        _noop.create_particle()
        _noop.destroy_particle()
```

## An action on a particle moved by its caller

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        box = literal.LocalPosition("position<box>", constraints=(Carrier,))
        box.create_particle()
        box.particle.get_action(Carrier).get_interface_position(
            "position<run>"
        ).create_particle()
        box.particle.get_action(Carrier).run()
        box.particle.get_action(Carrier).get_interface_position(
            "position<result>"
        ).particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).create_particle()
        box.particle.get_action(Carrier).get_interface_position(
            "position<result>"
        ).particle.get_action(Worker).run()
        box.particle.get_action(Carrier).get_interface_position(
            "position<result>"
        ).destroy_particle()
        box.destroy_particle()
```

### carrier.dfn

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

```python
class Carrier(literal.Action):
    def run(self):
        self.get_interface_position("position<source>").create_particle()
        self.get_interface_position("position<source>").move_particle_to(
            self.get_interface_position("position<result>")
        )
        self.get_interface_position("position<run>").destroy_particle()
```

### worker.dfn

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

```python
class Worker(literal.Action):
    def run(self):
        self.get_interface_position("position<run>").destroy_particle()
```

## A caller contributes a child Destroy

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/a>.
```

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/target>.
```

### test.dfn

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

```python
import local.my_domain_com.my_lib.triggered


class Test(literal.Action):
    def run(self):
        source = literal.LocalPosition("position<source>", constraints=(A,))
        source.create_particle()
        source.particle.get_position(A).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Triggered).get_interface_position(
                "position<run>"
            )
        )
        self.on_particle.get_action(Triggered).run(TriggeredDestructionContracts())


class TriggeredDestructionContracts(
    local.my_domain_com.my_lib.triggered.TriggeredDestructionContracts
):
    def destroy_position_run(self, particle):
        particle.get_position(A).destroy_particle()
```

### triggered.dfn

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

```python
class TriggeredDestructionContracts:
    def destroy_position_run(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = TriggeredDestructionContracts()


class Triggered(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        self.get_interface_position("position<run>").move_particle_to(
            self.on_particle.get_position(Target)
        )
        destruction_contracts.destroy_position_run(
            self.on_particle.get_position(Target).particle
        )
        self.on_particle.get_position(Target).destroy_particle()
```

## A Destruction Contract passed to an action on a local particle

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/target>.
```

### triggered.dfn

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

```python
class TriggeredDestructionContracts:
    def destroy_position_run(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = TriggeredDestructionContracts()


class Triggered(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        self.get_interface_position("position<run>").move_particle_to(
            self.on_particle.get_position(Target)
        )
        destruction_contracts.destroy_position_run(
            self.on_particle.get_position(Target).particle
        )
        self.on_particle.get_position(Target).destroy_particle()
```

### test.dfn

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

```python
import local.my_domain_com.my_lib.triggered


class Test(literal.Action):
    def run(self):
        triggered_parent = literal.LocalPosition(
            "position<triggered_parent>", constraints=(Triggered,)
        )
        source = literal.LocalPosition("position<source>", constraints=(A,))
        triggered_parent.create_particle()
        source.create_particle()
        source.particle.get_position(A).create_particle()
        source.move_particle_to(
            triggered_parent.particle.get_action(Triggered).get_interface_position(
                "position<run>"
            )
        )
        triggered_parent.particle.get_action(Triggered).run(
            TriggeredDestructionContracts()
        )
        triggered_parent.destroy_particle()


class TriggeredDestructionContracts(
    local.my_domain_com.my_lib.triggered.TriggeredDestructionContracts
):
    def destroy_position_run(self, particle):
        particle.get_position(A).destroy_particle()
```

## An action created and triggered by another action

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        maker_parent = literal.LocalPosition(
            "position<maker_parent>", constraints=(Maker,)
        )
        maker_parent.create_particle()
        maker_parent.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).create_particle()
        maker_parent.particle.get_action(Maker).run()
        maker_parent.particle.get_action(Maker).get_interface_position(
            "position<result>"
        ).destroy_particle()
        maker_parent.particle.get_action(Maker).get_interface_position(
            "position<run>"
        ).destroy_particle()
        maker_parent.destroy_particle()
```

### maker.dfn

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

```python
class Maker(literal.Action):
    def run(self):
        self.get_interface_position("position<result>").create_particle()
        self.get_interface_position("position<result>").particle.get_action(
            Worker
        ).get_interface_position("position<run>").create_particle()
        self.get_interface_position("position<result>").particle.get_action(
            Worker
        ).run()
```

### worker.dfn

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

```python
class Worker(literal.Action):
    def run(self):
        scratch = literal.LocalPosition("position<scratch>")
        scratch.create_particle()
        self.get_interface_position("position<run>").destroy_particle()
        scratch.destroy_particle()
```

## A callee Move after the caller empties its destination

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/dest>.
```

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        self.on_particle.get_position(Dest).create_particle()
        self.on_particle.get_position(Dest).destroy_particle()
        self.on_particle.get_action(Other).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.on_particle.get_action(Other).run()
        self.on_particle.get_position(Dest).destroy_particle()
        self.on_particle.get_action(Other).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
```

### other.dfn

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

```python
class Other(literal.Action):
    def run(self):
        src = literal.LocalPosition("position<src>")
        src.create_particle()
        src.move_particle_to(self.on_particle.get_position(Dest))
```

## Repeated Action Executions

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        gateway = literal.LocalPosition("position<gateway>", constraints=(Worker,))
        gateway.create_particle()
        gateway.particle.get_action(Worker).get_interface_position(
            "position<item>"
        ).create_particle()
        gateway.particle.get_action(Worker).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        gateway.particle.get_action(Worker).run()
        gateway.particle.get_action(Worker).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        gateway.particle.get_action(Worker).run()
        gateway.particle.get_action(Worker).get_interface_position(
            "position<item>"
        ).destroy_particle()
        gateway.destroy_particle()
```

### worker.dfn

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

```python
class Worker(literal.Action):
    def run(self):
        holder = literal.LocalPosition("position<holder>")
        self.get_interface_position("position<item>").move_particle_to(holder)
        holder.move_particle_to(self.get_interface_position("position<item>"))
        self.get_interface_position("position<trigger_pos>").destroy_particle()
```

## A Move preserves the action and its child particles

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/b>.
```

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        gateway = literal.LocalPosition("position<gateway>", constraints=(Other,))
        gateway.create_particle()
        gateway.particle.get_action(Other).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        gateway.particle.get_action(Other).run()
        gateway.particle.get_action(Other).get_interface_position(
            "position<dest>"
        ).particle.get_position(B).destroy_particle()
        gateway.particle.get_action(Other).get_interface_position(
            "position<dest>"
        ).particle.get_position(A).destroy_particle()
        gateway.particle.get_action(Other).get_interface_position(
            "position<dest>"
        ).destroy_particle()
        gateway.destroy_particle()
```

### other.dfn

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

```python
class Other(literal.Action):
    def run(self):
        self.get_interface_position("position<src>").create_particle()
        self.get_interface_position("position<src>").particle.get_position(
            A
        ).create_particle()
        self.get_interface_position("position<src>").particle.get_position(
            B
        ).create_particle()
        self.get_interface_position("position<src>").move_particle_to(
            self.get_interface_position("position<dest>")
        )
        self.get_interface_position("position<dest>").particle.get_action(
            Worker
        ).get_interface_position("position<run>").create_particle()
        self.get_interface_position("position<dest>").particle.get_action(Worker).run()
        self.get_interface_position("position<trigger_pos>").destroy_particle()
```

### worker.dfn

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

```python
class Worker(literal.Action):
    def run(self):
        scratch = literal.LocalPosition("position<scratch>")
        scratch.create_particle()
        scratch.destroy_particle()
        self.get_interface_position("position<run>").destroy_particle()
```

## A directly known Destructor executes sequentially

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        box = literal.LocalPosition("position<box>", constraints=(Destructor,))
        box.create_particle()
        box.particle.get_action(Destructor).run()
        box.destroy_particle()
```

### destructor.dfn

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

```python
class Destructor(literal.Action):
    def run(self):
        first = literal.LocalPosition("position<first>")
        second = literal.LocalPosition("position<second>")
        first.create_particle()
        first.destroy_particle()
        second.create_particle()
        second.destroy_particle()
```

## A moved particle and its two child particles are destroyed

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/a>.
define the potential position<my.domain.com:my_lib:/b>.
```

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        source = literal.LocalPosition("position<source>", constraints=(A, B))
        destination = literal.LocalPosition("position<destination>")
        source.create_particle()
        source.particle.get_position(A).create_particle()
        source.particle.get_position(B).create_particle()
        source.move_particle_to(destination)
        destination.particle.get_position(B).destroy_particle()
        destination.particle.get_position(A).destroy_particle()
        destination.destroy_particle()
```

## An intermediate action contributes a child Destroy

### Supporting positions

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

### test.dfn

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

```python
class Test(literal.Action):
    def run(self):
        second_holder = literal.LocalPosition("position<second_holder>")
        third_holder = literal.LocalPosition("position<third_holder>")
        self.on_particle.get_position(Input).create_particle()
        self.on_particle.get_position(Input).particle.get_position(
            Second
        ).create_particle()
        self.on_particle.get_position(Input).particle.get_position(
            Second
        ).move_particle_to(second_holder)
        second_holder.destroy_particle()
        self.on_particle.get_position(Input).particle.get_position(
            Third
        ).create_particle()
        self.on_particle.get_position(Input).particle.get_position(
            Third
        ).move_particle_to(third_holder)
        third_holder.destroy_particle()
        self.on_particle.get_action(MiddleAction).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.on_particle.get_action(MiddleAction).run()
        self.on_particle.get_action(MiddleAction).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()
```

### middle_action.dfn

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

```python
import local.my_domain_com.my_lib.inner


class MiddleAction(literal.Action):
    def run(self):
        self.on_particle.get_position(Input).particle.get_position(
            First
        ).create_particle()
        self.on_particle.get_action(Inner).get_interface_position(
            "position<trigger_pos>"
        ).create_particle()
        self.on_particle.get_action(Inner).run(InnerDestructionContracts())
        self.on_particle.get_action(Inner).get_interface_position(
            "position<trigger_pos>"
        ).destroy_particle()


class InnerDestructionContracts(
    local.my_domain_com.my_lib.inner.InnerDestructionContracts
):
    def destroy_global_position_input(self, particle):
        particle.get_position(First).destroy_particle()
```

### inner.dfn

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

```python
class InnerDestructionContracts:
    def destroy_global_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = InnerDestructionContracts()


class Inner(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        holder = literal.LocalPosition("position<holder>")
        self.on_particle.get_position(Input).move_particle_to(holder)
        destruction_contracts.destroy_global_position_input(holder.particle)
        holder.destroy_particle()
```

## Two callers contribute child Destroys to the same destruction

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/outer_child>.
define the potential position<my.domain.com:my_lib:/middle_child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</middle>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</outer_child>.
                it has the position</middle_child>.
            }
        }
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to action</middle>::position<input>.
    }
}
```

```python
import local.my_domain_com.my_lib.middle


class Outer(literal.Action):
    def run(self):
        source = literal.LocalPosition(
            "position<source>", constraints=(OuterChild, MiddleChild)
        )
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Middle).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Middle).run(MiddleDestructionContracts())


class MiddleDestructionContracts(
    local.my_domain_com.my_lib.middle.MiddleDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(OuterChild).destroy_particle()
```

### middle.dfn

```define
define the potential action<my.domain.com:my_lib:/middle> {
    it also assigns the action</inner>.
    define the position<input> {
        it may only contain particles where {
            it has the position</middle_child>.
        }
    }
    it happens when {
        the position<input> has a particle.
    } and it does {
        create a particle in position<input>::position</middle_child>.
        move the particle in position<input> to action</inner>::position<input>.
    }
}
```

```python
import local.my_domain_com.my_lib.inner


class MiddleDestructionContracts:
    def destroy_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = MiddleDestructionContracts()


class Middle(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        self.get_interface_position("position<input>").particle.get_position(
            MiddleChild
        ).create_particle()
        self.get_interface_position("position<input>").move_particle_to(
            self.on_particle.get_action(Inner).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Inner).run(
            InnerDestructionContracts(destruction_contracts.destroy_position_input)
        )


class InnerDestructionContracts(
    local.my_domain_com.my_lib.inner.InnerDestructionContracts
):
    def __init__(self, destroy_position_input):
        self._destroy_position_input = destroy_position_input

    def destroy_position_input(self, particle):
        self._destroy_position_input(particle)
        particle.get_position(MiddleChild).destroy_particle()
```

### inner.dfn

```define
define the potential action<my.domain.com:my_lib:/inner> {
    define the position<input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        define the position<holder>.
        move the particle in position<input> to position<holder>.
        destroy the particle in position<holder>.
    }
}
```

```python
class InnerDestructionContracts:
    def destroy_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = InnerDestructionContracts()


class Inner(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        holder = literal.LocalPosition("position<holder>")
        self.get_interface_position("position<input>").move_particle_to(holder)
        destruction_contracts.destroy_position_input(holder.particle)
        holder.destroy_particle()
```

## Separate contracted inputs share a local position name in Middle and Inner

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/outer_child>.
define the potential position<my.domain.com:my_lib:/middle_child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</middle>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</outer_child>.
                it has the position</middle_child>.
            }
        }
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to action</middle>::position<input>.
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to action</middle>::position<next_input>.
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to action</middle>::position<inner_input>.
        create a particle in action</middle>::position<run>.
        destroy the particle in action</middle>::position<run>.
    }
}
```

```python
import local.my_domain_com.my_lib.middle


class Outer(literal.Action):
    def run(self):
        source = literal.LocalPosition(
            "position<source>", constraints=(OuterChild, MiddleChild)
        )
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Middle).get_interface_position(
                "position<input>"
            )
        )
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Middle).get_interface_position(
                "position<next_input>"
            )
        )
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Middle).get_interface_position(
                "position<inner_input>"
            )
        )
        self.on_particle.get_action(Middle).get_interface_position(
            "position<run>"
        ).create_particle()
        self.on_particle.get_action(Middle).run(MiddleDestructionContracts())
        self.on_particle.get_action(Middle).get_interface_position(
            "position<run>"
        ).destroy_particle()


class MiddleDestructionContracts(
    local.my_domain_com.my_lib.middle.MiddleDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(OuterChild).destroy_particle()

    def destroy_position_next_input(self, particle):
        particle.get_position(OuterChild).destroy_particle()

    def destroy_position_inner_input(self, particle):
        particle.get_position(OuterChild).destroy_particle()
```

### middle.dfn

```define
define the potential action<my.domain.com:my_lib:/middle> {
    it also assigns the action</inner>.
    define the position<input>.
    define the position<next_input>.
    define the position<inner_input> {
        it may only contain particles where {
            it has the position</middle_child>.
        }
    }
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<holder>.
        move the particle in position<input> to position<holder>.
        destroy the particle in position<holder>.
        move the particle in position<next_input> to position<holder>.
        destroy the particle in position<holder>.
        create a particle in position<inner_input>::position</middle_child>.
        move the particle in position<inner_input> to action</inner>::position<input>.
    }
}
```

```python
import local.my_domain_com.my_lib.inner


class MiddleDestructionContracts:
    def destroy_position_input(self, _particle):
        pass

    def destroy_position_next_input(self, _particle):
        pass

    def destroy_position_inner_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = MiddleDestructionContracts()


class Middle(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        holder = literal.LocalPosition("position<holder>")
        self.get_interface_position("position<input>").move_particle_to(holder)
        destruction_contracts.destroy_position_input(holder.particle)
        holder.destroy_particle()
        self.get_interface_position("position<next_input>").move_particle_to(holder)
        destruction_contracts.destroy_position_next_input(holder.particle)
        holder.destroy_particle()
        self.get_interface_position("position<inner_input>").particle.get_position(
            MiddleChild
        ).create_particle()
        self.get_interface_position("position<inner_input>").move_particle_to(
            self.on_particle.get_action(Inner).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Inner).run(
            InnerDestructionContracts(
                destruction_contracts.destroy_position_inner_input
            )
        )


class InnerDestructionContracts(
    local.my_domain_com.my_lib.inner.InnerDestructionContracts
):
    def __init__(self, destroy_position_input):
        self._destroy_position_input = destroy_position_input

    def destroy_position_input(self, particle):
        self._destroy_position_input(particle)
        particle.get_position(MiddleChild).destroy_particle()
```

### inner.dfn

```define
define the potential action<my.domain.com:my_lib:/inner> {
    define the position<input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        define the position<holder>.
        move the particle in position<input> to position<holder>.
        destroy the particle in position<holder>.
    }
}
```

```python
class InnerDestructionContracts:
    def destroy_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = InnerDestructionContracts()


class Inner(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        holder = literal.LocalPosition("position<holder>")
        self.get_interface_position("position<input>").move_particle_to(holder)
        destruction_contracts.destroy_position_input(holder.particle)
        holder.destroy_particle()
```

## An implied action destroys implied and interface positions both named item

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/item>.
define the potential position<my.domain.com:my_lib:/outer_child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the position</item>.
    it also assigns the action</worker>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</outer_child>.
            }
        }
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to position</item>.
        create a particle in position<source>.
        create a particle in position<source>::position</outer_child>.
        move the particle in position<source> to action</worker>::position<item>.
        create a particle in action</worker>::position<run>.
        destroy the particle in action</worker>::position<run>.
    }
}
```

```python
import local.my_domain_com.my_lib.worker


class Outer(literal.Action):
    def run(self):
        source = literal.LocalPosition("position<source>", constraints=(OuterChild,))
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(self.on_particle.get_position(Item))
        source.create_particle()
        source.particle.get_position(OuterChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position(
                "position<item>"
            )
        )
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).create_particle()
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts())
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).destroy_particle()


class WorkerDestructionContracts(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def destroy_global_position_item(self, particle):
        particle.get_position(OuterChild).destroy_particle()

    def destroy_position_item(self, particle):
        particle.get_position(OuterChild).destroy_particle()
```

### worker.dfn

```define
define the potential action<my.domain.com:my_lib:/worker> {
    it also assigns the position</item>.
    define the position<item>.
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        destroy the particle in position</item>.
        destroy the particle in position<item>.
    }
}
```

```python
class WorkerDestructionContracts:
    def destroy_global_position_item(self, _particle):
        pass

    def destroy_position_item(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = WorkerDestructionContracts()


class Worker(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        destruction_contracts.destroy_global_position_item(
            self.on_particle.get_position(Item).particle
        )
        self.on_particle.get_position(Item).destroy_particle()
        destruction_contracts.destroy_position_item(
            self.get_interface_position("position<item>").particle
        )
        self.get_interface_position("position<item>").destroy_particle()
```

## Different, partial, and absent contributions across multiple invocations

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/first_child>.
define the potential position<my.domain.com:my_lib:/second_child>.
define the potential position<my.domain.com:my_lib:/third_child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</worker>.
    it also assigns the action</other>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</first_child>.
                it has the position</second_child>.
                it has the position</third_child>.
            }
        }
        create a particle in position<source>.
        create a particle in position<source>::position</first_child>.
        create a particle in action</worker>::position<other_input>.
        move the particle in position<source> to action</worker>::position<input>.
        create a particle in position<source>.
        create a particle in position<source>::position</second_child>.
        create a particle in action</worker>::position<other_input>.
        move the particle in position<source> to action</worker>::position<input>.
        create a particle in position<source>.
        create a particle in position<source>::position</third_child>.
        move the particle in position<source> to action</other>::position<input>.
        create a particle in action</worker>::position<other_input>.
        create a particle in action</worker>::position<input>.
    }
}
```

```python
import local.my_domain_com.my_lib.worker
import local.my_domain_com.my_lib.other


class Outer(literal.Action):
    def run(self):
        source = literal.LocalPosition(
            "position<source>", constraints=(FirstChild, SecondChild, ThirdChild)
        )
        source.create_particle()
        source.particle.get_position(FirstChild).create_particle()
        self.on_particle.get_action(Worker).get_interface_position(
            "position<other_input>"
        ).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts())
        source.create_particle()
        source.particle.get_position(SecondChild).create_particle()
        self.on_particle.get_action(Worker).get_interface_position(
            "position<other_input>"
        ).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts_2())
        source.create_particle()
        source.particle.get_position(ThirdChild).create_particle()
        source.move_particle_to(
            self.on_particle.get_action(Other).get_interface_position(
                "position<input>"
            )
        )
        self.on_particle.get_action(Other).run(OtherDestructionContracts())
        self.on_particle.get_action(Worker).get_interface_position(
            "position<other_input>"
        ).create_particle()
        self.on_particle.get_action(Worker).get_interface_position(
            "position<input>"
        ).create_particle()
        self.on_particle.get_action(Worker).run()


class WorkerDestructionContracts(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(FirstChild).destroy_particle()


class WorkerDestructionContracts_2(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(SecondChild).destroy_particle()


class OtherDestructionContracts(
    local.my_domain_com.my_lib.other.OtherDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(ThirdChild).destroy_particle()
```

### worker.dfn

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<input>.
    define the position<other_input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        destroy the particle in position<input>.
        destroy the particle in position<other_input>.
    }
}
```

```python
class WorkerDestructionContracts:
    def destroy_position_input(self, _particle):
        pass

    def destroy_position_other_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = WorkerDestructionContracts()


class Worker(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        destruction_contracts.destroy_position_input(
            self.get_interface_position("position<input>").particle
        )
        self.get_interface_position("position<input>").destroy_particle()
        destruction_contracts.destroy_position_other_input(
            self.get_interface_position("position<other_input>").particle
        )
        self.get_interface_position("position<other_input>").destroy_particle()
```

### other.dfn

```define
define the potential action<my.domain.com:my_lib:/other> {
    define the position<input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        destroy the particle in position<input>.
    }
}
```

```python
class OtherDestructionContracts:
    def destroy_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = OtherDestructionContracts()


class Other(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        destruction_contracts.destroy_position_input(
            self.get_interface_position("position<input>").particle
        )
        self.get_interface_position("position<input>").destroy_particle()
```

## Known and contributed Destructors finish before parent and child destruction

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</worker>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the action</known_destructor>.
                it has the action</parent_destructor>.
                it has the position</child>.
            }
        }
        define the position<child_source> {
            it may only contain particles where {
                it has the action</child_destructor>.
            }
        }
        create a particle in position<source>.
        create a particle in position<child_source>.
        move the particle in position<child_source> to position<source>::position</child>.
        move the particle in position<source> to action</worker>::position<input>.
    }
}
```

```python
import local.my_domain_com.my_lib.worker


class Outer(literal.Action):
    def run(self):
        source = literal.LocalPosition(
            "position<source>", constraints=(KnownDestructor, ParentDestructor, Child)
        )
        child_source = literal.LocalPosition(
            "position<child_source>", constraints=(ChildDestructor,)
        )
        source.create_particle()
        child_source.create_particle()
        child_source.move_particle_to(source.particle.get_position(Child))
        source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position("position<input>")
        )
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts())


class WorkerDestructionContracts(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def run_destructors_position_input(self, particle):
        particle.get_action(ParentDestructor).run()
        particle.get_position(Child).particle.get_action(ChildDestructor).run()

    def destroy_position_input(self, particle):
        particle.get_position(Child).destroy_particle()
```

### worker.dfn

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<input> {
        it may only contain particles where {
            it has the action</known_destructor>.
        }
    }
    it happens when {
        the position<input> has a particle.
    } and it does {
        destroy the particle in position<input>.
    }
}
```

```python
class WorkerDestructionContracts:
    def run_destructors_position_input(self, _particle):
        pass

    def destroy_position_input(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = WorkerDestructionContracts()


class Worker(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        self.get_interface_position("position<input>").particle.get_action(
            KnownDestructor
        ).run()
        destruction_contracts.run_destructors_position_input(
            self.get_interface_position("position<input>").particle
        )
        destruction_contracts.destroy_position_input(
            self.get_interface_position("position<input>").particle
        )
        self.get_interface_position("position<input>").destroy_particle()
```

### known_destructor.dfn

```define
define the potential action<my.domain.com:my_lib:/known_destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
        destroy the particle in position<work>.
    }
}
```

```python
class KnownDestructor(literal.Action):
    def run(self):
        work = literal.LocalPosition("position<work>")
        work.create_particle()
        work.destroy_particle()
```

### parent_destructor.dfn

```define
define the potential action<my.domain.com:my_lib:/parent_destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
        destroy the particle in position<work>.
    }
}
```

```python
class ParentDestructor(literal.Action):
    def run(self):
        work = literal.LocalPosition("position<work>")
        work.create_particle()
        work.destroy_particle()
```

### child_destructor.dfn

```define
define the potential action<my.domain.com:my_lib:/child_destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
        destroy the particle in position<work>.
    }
}
```

```python
class ChildDestructor(literal.Action):
    def run(self):
        work = literal.LocalPosition("position<work>")
        work.create_particle()
        work.destroy_particle()
```

## Two destructions in input retain distinct contracted origins

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/first_child>.
define the potential position<my.domain.com:my_lib:/second_child>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</worker>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<first_source> {
            it may only contain particles where {
                it has the position</first_child>.
            }
        }
        define the position<second_source> {
            it may only contain particles where {
                it has the position</second_child>.
            }
        }
        create a particle in position<first_source>.
        create a particle in position<first_source>::position</first_child>.
        create a particle in position<second_source>.
        create a particle in position<second_source>::position</second_child>.
        move the particle in position<first_source> to action</worker>::position<input>.
        move the particle in position<second_source> to action</worker>::position<reserve>.
        create a particle in action</worker>::position<run>.
        destroy the particle in action</worker>::position<run>.
    }
}
```

```python
import local.my_domain_com.my_lib.worker


class Outer(literal.Action):
    def run(self):
        first_source = literal.LocalPosition(
            "position<first_source>", constraints=(FirstChild,)
        )
        second_source = literal.LocalPosition(
            "position<second_source>", constraints=(SecondChild,)
        )
        first_source.create_particle()
        first_source.particle.get_position(FirstChild).create_particle()
        second_source.create_particle()
        second_source.particle.get_position(SecondChild).create_particle()
        first_source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position("position<input>")
        )
        second_source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position("position<reserve>")
        )
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).create_particle()
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts())
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).destroy_particle()


class WorkerDestructionContracts(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def destroy_position_input(self, particle):
        particle.get_position(FirstChild).destroy_particle()

    def destroy_position_reserve(self, particle):
        particle.get_position(SecondChild).destroy_particle()
```

### worker.dfn

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<input>.
    define the position<reserve>.
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        destroy the particle in position<input>.
        move the particle in position<reserve> to position<input>.
        destroy the particle in position<input>.
    }
}
```

```python
class WorkerDestructionContracts:
    def destroy_position_input(self, _particle):
        pass

    def destroy_position_reserve(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = WorkerDestructionContracts()


class Worker(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        destruction_contracts.destroy_position_input(
            self.get_interface_position("position<input>").particle
        )
        self.get_interface_position("position<input>").destroy_particle()
        self.get_interface_position("position<reserve>").move_particle_to(
            self.get_interface_position("position<input>")
        )
        destruction_contracts.destroy_position_reserve(
            self.get_interface_position("position<input>").particle
        )
        self.get_interface_position("position<input>").destroy_particle()
```

## One destruction includes particles received through two contracted positions

### Supporting positions

```define
define the potential position<my.domain.com:my_lib:/left>.
define the potential position<my.domain.com:my_lib:/right>.
define the potential position<my.domain.com:my_lib:/extra>.
```

### outer.dfn

```define
define the potential action<my.domain.com:my_lib:/outer> {
    it also assigns the action</worker>.
    it happens when {
        this particle is created.
    } and it does {
        define the position<first_source> {
            it may only contain particles where {
                it has the action</first_destructor>.
                it has the position</extra>.
            }
        }
        define the position<second_source> {
            it may only contain particles where {
                it has the action</second_destructor>.
                it has the position</extra>.
            }
        }
        create a particle in position<first_source>.
        create a particle in position<first_source>::position</extra>.
        create a particle in position<second_source>.
        create a particle in position<second_source>::position</extra>.
        move the particle in position<first_source> to action</worker>::position<first>.
        move the particle in position<second_source> to action</worker>::position<second>.
        create a particle in action</worker>::position<run>.
        destroy the particle in action</worker>::position<run>.
    }
}
```

```python
import local.my_domain_com.my_lib.worker


class Outer(literal.Action):
    def run(self):
        first_source = literal.LocalPosition(
            "position<first_source>", constraints=(FirstDestructor, Extra)
        )
        second_source = literal.LocalPosition(
            "position<second_source>", constraints=(SecondDestructor, Extra)
        )
        first_source.create_particle()
        first_source.particle.get_position(Extra).create_particle()
        second_source.create_particle()
        second_source.particle.get_position(Extra).create_particle()
        first_source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position("position<first>")
        )
        second_source.move_particle_to(
            self.on_particle.get_action(Worker).get_interface_position("position<second>")
        )
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).create_particle()
        self.on_particle.get_action(Worker).run(WorkerDestructionContracts())
        self.on_particle.get_action(Worker).get_interface_position(
            "position<run>"
        ).destroy_particle()


class WorkerDestructionContracts(
    local.my_domain_com.my_lib.worker.WorkerDestructionContracts
):
    def run_destructors_position_first(self, particle):
        particle.get_action(FirstDestructor).run()

    def run_destructors_position_second(self, particle):
        particle.get_action(SecondDestructor).run()

    def destroy_position_first(self, particle):
        particle.get_position(Extra).destroy_particle()

    def destroy_position_second(self, particle):
        particle.get_position(Extra).destroy_particle()
```

### worker.dfn

```define
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<first>.
    define the position<second>.
    define the position<run>.
    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<holder> {
            it may only contain particles where {
                it has the position</left>.
                it has the position</right>.
            }
        }
        create a particle in position<holder>.
        move the particle in position<first> to position<holder>::position</left>.
        move the particle in position<second> to position<holder>::position</right>.
        destroy the particle in position<holder>.
    }
}
```

```python
class WorkerDestructionContracts:
    def run_destructors_position_first(self, _particle):
        pass

    def run_destructors_position_second(self, _particle):
        pass

    def destroy_position_first(self, _particle):
        pass

    def destroy_position_second(self, _particle):
        pass



_DEFAULT_DESTRUCTION_CONTRACTS = WorkerDestructionContracts()


class Worker(literal.Action):
    def run(self, destruction_contracts=_DEFAULT_DESTRUCTION_CONTRACTS):
        holder = literal.LocalPosition("position<holder>", constraints=(Left, Right))
        holder.create_particle()
        self.get_interface_position("position<first>").move_particle_to(
            holder.particle.get_position(Left)
        )
        self.get_interface_position("position<second>").move_particle_to(
            holder.particle.get_position(Right)
        )
        destruction_contracts.run_destructors_position_first(
            holder.particle.get_position(Left).particle
        )
        destruction_contracts.run_destructors_position_second(
            holder.particle.get_position(Right).particle
        )
        destruction_contracts.destroy_position_first(
            holder.particle.get_position(Left).particle
        )
        destruction_contracts.destroy_position_second(
            holder.particle.get_position(Right).particle
        )
        holder.particle.get_position(Left).destroy_particle()
        holder.particle.get_position(Right).destroy_particle()
        holder.destroy_particle()
```

### first_destructor.dfn

```define
define the potential action<my.domain.com:my_lib:/first_destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
        destroy the particle in position<work>.
    }
}
```

```python
class FirstDestructor(literal.Action):
    def run(self):
        work = literal.LocalPosition("position<work>")
        work.create_particle()
        work.destroy_particle()
```

### second_destructor.dfn

```define
define the potential action<my.domain.com:my_lib:/second_destructor> {
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
        destroy the particle in position<work>.
    }
}
```

```python
class SecondDestructor(literal.Action):
    def run(self):
        work = literal.LocalPosition("position<work>")
        work.create_particle()
        work.destroy_particle()
```
