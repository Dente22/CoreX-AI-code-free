'use strict';

const fs = require('fs');
const path = require('path');

const FRONTEND_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..');

const REQUIRED_EXTRA_RESOURCES = [
  { from: '../core_x_agents', to: 'core_x_agents' },
  { from: '../core_x_skills', to: 'core_x_skills' },
  { from: '../core_x_knowledge', to: 'core_x_knowledge' },
  { from: '../backend', to: 'backend' },
  { from: '../main.py', to: 'main.py' },
];

function main() {
  const pkg = JSON.parse(
    fs.readFileSync(path.join(FRONTEND_ROOT, 'package.json'), 'utf8'),
  );
  const extra = pkg.build?.extraResources || [];

  for (const required of REQUIRED_EXTRA_RESOURCES) {
    const found = extra.some(
      (item) => item.from === required.from && item.to === required.to,
    );
    if (!found) {
      throw new Error(
        `package.json extraResources missing ${required.from} -> ${required.to}`,
      );
    }

    const source = path.resolve(
      FRONTEND_ROOT,
      required.from.replace(/^\.\.\//, '../'),
    );
    if (!fs.existsSync(source)) {
      throw new Error(`Installer source missing: ${source}`);
    }
  }

  const agentsDir = path.join(REPO_ROOT, 'core_x_agents');
  const teamsDir = path.join(agentsDir, 'teams');
  const agentMd = fs.readdirSync(agentsDir).filter((f) => f.endsWith('.md'));
  const teamJson = fs.readdirSync(teamsDir).filter((f) => f.endsWith('.json'));

  if (agentMd.length < 5) {
    throw new Error(`Expected >=5 agent .md files, found ${agentMd.length}`);
  }
  if (teamJson.length < 2) {
    throw new Error(`Expected >=2 team .json files, found ${teamJson.length}`);
  }

  console.log(
    `[CoreX] Installer library OK: ${agentMd.length} agents, ${teamJson.length} teams`,
  );
}

main();
