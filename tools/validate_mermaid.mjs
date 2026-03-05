import { parse } from "@a24z/mermaid-parser";
import { text } from "node:stream/consumers";

const input = await text(process.stdin);

const result = await parse(input);
if (!result.valid) {
  console.error(result.error);
  process.exit(1);
}
