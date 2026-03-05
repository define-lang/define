import { parse } from "@a24z/mermaid-parser";
import assert from "node:assert";

const valid = await parse("flowchart LR\n    A --> B\n");
assert.strictEqual(valid.valid, true);

const invalid = await parse("not mermaid at all");
assert.strictEqual(invalid.valid, false);
assert.strictEqual(invalid.error, "Unknown diagram type");
