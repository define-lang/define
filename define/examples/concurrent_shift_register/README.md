# Concurrent shift register in Define

A 3-cell shift register. `/register` represents the register itself. It is set
up by `action</construct>` which puts it into a valid initial state (it has 3
bits). It has an `action</shift>` that shifts each bit to the right and pushes
the rightmost bit off the register (destroys it).

`action</main>` shifts the bits twice. This results in a total action graph that
looks like:

```mermaid
flowchart
    CrReg["create(register)"] --> Cr0["create(bit0)"]
    CrReg --> Cr1["create(bit1)"]
    CrReg --> Cr2["create(bit2)"]
    CrReg --> INa["create(input) #1"]

    Cr0 --> C1a["move(bit0 → next1) #1"]
    Cr1 --> C2a["move(bit1 → next2) #1"]
    Cr2 --> D2a["drop(bit2) #1"]
    INa --> I0a["move(input → next0) #1"]

    I0a --> K0a["move(next0 → bit0) #1"]
    C1a --> K0a
    C1a --> K1a["move(next1 → bit1) #1"]
    C2a --> K1a
    C2a --> K2a["move(next2 → bit2) #1"]
    D2a --> K2a

    I0a --> INb["create(input) #2"]
    K0a --> C1b["move(bit0 → next1) #2"]
    K1a --> C2b["move(bit1 → next2) #2"]
    K2a --> D2b["drop(bit2) #2"]
    INb --> I0b["move(input → next0) #2"]

    I0b --> K0b["move(next0 → bit0) #2"]
    C1b --> K0b
    C1b --> K1b["move(next1 → bit1) #2"]
    C2b --> K1b
    C2b --> K2b["move(next2 → bit2) #2"]
    D2b --> K2b
```

Each step runs as soon as the steps it depends on are done. A step never waits
for anything else, so many steps happen at the same time.

When the register is created in `action</construct>`, its three cells get their
bits at the same time, and the first input bit is created right then too.

A cell can be moved into the scratch buffer as soon as it has its bit, so the
first shift's three moves, plus dropping the bit that falls off the end, all
happen together (right after each cell gets its bit).

Moving a bit back into a cell from the buffer waits only for the two steps that
give it what it needs. For example, writing the new value of cell 0 waits for
just two things: the move of the input and cell 0 into the buffer. It does not
wait for cells 1 or 2.

The second shift does not wait for the whole first shift to finish. Each cell
moves on by itself. The moment the first shift finishes writing a cell, the
second clock can start reading that same cell, even while the first clock is
still working on the other cells. And because the first clock uses up the input
bit early, the second input bit can be created right away, while the first clock
is still running.

So the two clocks overlap instead of running one fully after the other. The only
thing that sets the total time is the longest chain of steps that truly have to
happen in order, which is about six steps long (for example, following one cell
all the way through both clocks). There is no point where everything stops and
waits for everything else.
