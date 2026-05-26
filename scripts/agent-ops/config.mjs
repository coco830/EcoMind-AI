import path from 'node:path';
import process from 'node:process';

const home = process.env.USERPROFILE || process.env.HOME || '';

function splitEnvList(value) {
  if (!value) {
    return [];
  }

  return value
    .split(path.delimiter)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

// AI 操作层配置。复制到项目后可按机器和仓库调整。
export const agentOpsConfig = {
  skillsIndexPath: 'docs/agents/skills-index.md',
  // 复制到目标项目后，索引会按当前机器和项目的真实技能库生成。
  skillRoots: [
    ...splitEnvList(process.env.ENVIRO_SKILL_ROOTS),
    path.join(home, '.codex', 'skills'),
    path.join(home, '.agents', 'skills'),
    path.join(process.cwd(), '.agents', 'skills'),
    path.join(process.cwd(), '.claude', 'skills'),
  ],
  autonomy: {
    green: ['局部重构', '测试补齐', '文档同步', '非破坏性脚本修复'],
    yellow: ['新增依赖', '公共接口调整', '验证策略调整', '跨模块改动'],
    red: ['真实密钥', '生产数据', '删除数据', '权限变更', '主干推送', '正式发布'],
  },
  stopConditions: [
    '需要真实账号、真实密钥或生产数据',
    '会删除数据、改迁移、改权限或发布版本',
    '连续 3 次修复同一失败仍失败',
    '需求与 BDD、README 或 AGENTS 明确冲突',
  ],
};
