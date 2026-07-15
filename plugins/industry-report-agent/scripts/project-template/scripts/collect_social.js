/**
 * Agent 03 - 用户声音采集
 * 使用搜索结果页聚合公开社区讨论，规避直接访问登录墙页面导致的空数据。
 * 运行方式: ego-browser nodejs < scripts/collect_social.js
 */

const fs = require('fs');
const path = require('path');

const AGENT_DIR = process.env.AGENT_DIR || path.resolve(__dirname, '..');
const config = JSON.parse(fs.readFileSync(path.join(AGENT_DIR, 'config.json'), 'utf8'));
const outputDir = path.join(AGENT_DIR, 'output', 'raw');

if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

const { industry, year } = config.target;
const taskName = `collect-social-${industry}-${year}`;
await useOrCreateTaskSpace(taskName);

const results = {
  timestamp: new Date().toISOString(),
  industry,
  platforms: {},
  pain_points_raw: []
};

const COMMUNITY_SOURCES = (config.platform_queries || []).map(source => ({
  key: source.platform,
  label: source.platform,
  site: source.site || '',
  keywords: source.queries || []
}));

function dedupe(items) {
  const seen = new Set();
  return items.filter(item => {
    const key = `${item.title || ''}::${item.url || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function searchCommunity(source, keyword) {
  const query = `site:${source.site} ${keyword}`;
  await openOrReuseTab(
    `https://www.baidu.com/s?wd=${encodeURIComponent(query)}`,
    { wait: true, timeout: 20 }
  );
  await wait(2);

  const items = await js(String.raw`(() => {
    const nodes = [...document.querySelectorAll('h3.t, .result h3, .c-title, .result-title')];
    return nodes.slice(0, 6).map(el => {
      const link = el.querySelector('a') || el.closest('a');
      return {
        title: (el.innerText || '').trim(),
        url: link ? link.href : ''
      };
    }).filter(item => item.title.length > 5);
  })()`);

  return items.map(item => ({
    ...item,
    source: source.label,
    keyword
  }));
}

cliLog('📡 聚合公开社区用户声音...');

for (const source of COMMUNITY_SOURCES) {
  if (!source.site) {
    cliLog(`\n[${source.label}] 未配置 site，legacy fallback 跳过；默认 collect 不需要该字段`);
    continue;
  }
  cliLog(`\n[${source.label}] 搜索社区讨论...`);
  const collected = [];

  for (const keyword of source.keywords) {
    try {
      const items = await searchCommunity(source, keyword);
      collected.push(...items);
      cliLog(`  ✅ "${keyword}": ${items.length} 条`);
      await wait(1);
    } catch (e) {
      cliLog(`  ⚠️ "${keyword}" 异常: ${e.message}`);
    }
  }

  results.platforms[source.key] = dedupe(collected).slice(0, 10);
  cliLog(`  📦 ${source.label} 去重后保留 ${results.platforms[source.key].length} 条`);
}

const outputFile = path.join(outputDir, 'social_data.json');
fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));

const total = Object.values(results.platforms).reduce((sum, items) => sum + items.length, 0);
cliLog(`\n💾 已保存至 ${outputFile}`);
cliLog(`📊 总计: ${total} 条社区结果`);

await completeTaskSpace(taskName, { keep: false });
