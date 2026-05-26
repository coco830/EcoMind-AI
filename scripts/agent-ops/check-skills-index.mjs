import { existsSync, readFileSync } from 'node:fs';
import process from 'node:process';
import { agentOpsConfig } from './config.mjs';
import { buildSkillsIndexMarkdown } from './generate-skills-index.mjs';

// 检查 skills index 是否和当前技能库一致。
// 用于发现全局/用户级/project skills 新增或删除后忘记刷新索引的问题。
if (!existsSync(agentOpsConfig.skillsIndexPath)) {
  console.error(`${agentOpsConfig.skillsIndexPath} is missing. Run python .\\verify.py agents --write.`);
  process.exit(1);
}

const current = readFileSync(agentOpsConfig.skillsIndexPath, 'utf8');
const expected = buildSkillsIndexMarkdown().markdown;

if (current !== expected) {
  console.error(`${agentOpsConfig.skillsIndexPath} is out of date. Run python .\\verify.py agents --write.`);
  process.exit(1);
}

console.log(`${agentOpsConfig.skillsIndexPath} is up to date.`);
