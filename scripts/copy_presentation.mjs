import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptsDir, "..");
const sourcePath = path.join(projectRoot, "presentation", "holyship-presentation.html");
const targetProject = process.argv[2] === "outlook-addin" ? "outlook-addin" : "frontend";
const outputDir = path.join(projectRoot, targetProject, "dist", "presentation");
const outputPath = path.join(outputDir, "holyship-presentation.html");

const source = await readFile(sourcePath, "utf8");
const deployed = source.replaceAll("../frontend/public/holyship-logo.png", "../holyship-logo.png");

await mkdir(outputDir, { recursive: true });
await writeFile(outputPath, deployed, "utf8");
console.log(`Copied presentation to ${path.relative(projectRoot, outputPath)}`);
