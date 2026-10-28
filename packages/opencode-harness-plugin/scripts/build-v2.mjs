// Build only the V2 adapter and the existing transport; never rewrite dist/ (V1).
import { readFile, writeFile, mkdir, copyFile } from "node:fs/promises"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"
import { resolve, join } from "node:path"

const root = fileURLToPath(new URL("../", import.meta.url))
const require = createRequire(import.meta.url)
const compiler = process.argv[2] || process.env.HARNESS_TYPESCRIPT_PATH || "typescript"
const ts = require(compiler)
const out = join(root, "dist-v2")
await mkdir(join(out, "v2"), { recursive: true })
await mkdir(join(out, "bridge"), { recursive: true })
await copyFile(join(root, "src/v2/index.js"), join(out, "v2/index.js"))
for (const name of ["bridge", "protocol"]) {
  const source = await readFile(join(root, `src/bridge/${name}.ts`), "utf8")
  const result = ts.transpileModule(source, {
    fileName: `${name}.ts`, reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, strict: true },
  })
  const errors = result.diagnostics?.filter((item) => item.category === ts.DiagnosticCategory.Error) ?? []
  if (errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(errors, {
    getCurrentDirectory: () => resolve(root), getCanonicalFileName: (path) => path, getNewLine: () => "\n",
  }))
  await writeFile(join(out, `bridge/${name}.js`), result.outputText, "utf8")
}
console.log(`V2 build: ${join(out, "v2/index.js")} (transpile only, not SDK type certification)`)
