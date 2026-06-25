# TCP connection: a state machine in Define

Each TCP state is a position, and each transition is an action that moves the
connection's single token particle from one state position to another.
`main.dfn` is the entry point and `driver.dfn` runs one connection through a
server lifecycle (CLOSED → LISTEN → SYN_RECEIVED → ESTABLISHED → CLOSE_WAIT →
LAST_ACK → CLOSED).
