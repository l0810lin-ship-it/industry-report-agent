/**
 * Agent 02 - 竞品 AI 能力扫描
 * 系统扫描各主要平台的 AI 功能布局
 * 运行方式: ego-browser nodejs < scripts/scan_competitors.js
 */

const fs = require('fs');
const path = require('path');

const AGENT_DIR = process.env.AGENT_DIR || path.resolve(__dirname, '..');
const config = JSON.parse(fs.readFileSync(path.join(AGENT_DIR, 'config.json'), 'utf8'));
const outputDir = path.join(AGENT_DIR, 'output', 'raw');

if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

const { year } = config.target;
const taskName = `scan-competitors-${year}`;
const task = await useOrCreateTaskSpace(taskName);

const results = {
  timestamp: new Date().toISOString(),
  competitors: {},
  ai_feature_matrix: {}
};

// 竞品信息搜索维度
const AI_DIMENSIONS = [
  'AI 推荐', '智能搜索', '评价摘要', '个性化', '智能客服', '内容生成', '价格预测', '语音交互'
];

// ── 搜索各竞品 AI 战略新闻 ──────────────────────────
for (const competitor of config.competitors) {
  cliLog(`\n🔍 扫描竞品: ${competitor}`);
  const competitorData = { news: [], features: [], ai_score: {} };

  // 旧版浏览器 fallback：逐条执行当前配置中的竞品查询
  try {
    const keywords = config.competitor_keywords[competitor] || [`${competitor} AI 功能`];
    for (const searchKeyword of keywords) {
      await openOrReuseTab(
        `https://www.baidu.com/s?wd=${encodeURIComponent(searchKeyword)}`,
        { wait: true, timeout: 20 }
      );
      await wait(2);

      const newsItems = await js(String.raw`(() => {
        const items = [...document.querySelectorAll('h3.t, .result h3, .c-title, .result-title')];
        return items.slice(0, 8).map(el => ({
          title: el.innerText.trim(),
          url: el.querySelector('a') ? el.querySelector('a').href : ''
        })).filter(i => i.title.length > 5);
      })()`);

      competitorData.news.push(...newsItems.map(item => ({ ...item, query: searchKeyword })));
      cliLog(`  ✅ "${searchKeyword}": ${newsItems.length} 条新闻`);
    }
  } catch (e) {
    cliLog(`  ⚠️ 搜索异常: ${e.message}`);
  }

  // 36kr 搜索竞品专题
  try {
    await openOrReuseTab(
      `https://36kr.com/search/articles/${encodeURIComponent(competitor + ' AI')}`,
      { wait: true, timeout: 25 }
    );
    await wait(2);

    const krItems = await js(String.raw`(() => {
      const cards = [...document.querySelectorAll('h3, .article-item-title, .title')];
      return cards.slice(0, 6).map(el => ({
        title: el.innerText.trim(),
        source: '36kr'
      })).filter(i => i.title.length > 5);
    })()`);

    competitorData.news.push(...krItems);
  } catch (e) {
    cliLog(`  ⚠️ 36kr 竞品搜索跳过`);
  }

  results.competitors[competitor] = competitorData;
  await wait(1);
}

// ── 生成 AI 功能对比矩阵（基于采集数据的初步评分框架）──
cliLog('\n📊 生成竞品能力框架...');
results.ai_feature_matrix = {
  dimensions: AI_DIMENSIONS,
  note: '以下评分由 analyze.py 中 Claude 根据采集数据自动生成，1=基础能力，5=行业领先',
  scores: {}
};

for (const competitor of config.competitors) {
  results.ai_feature_matrix.scores[competitor] = {};
  for (const dim of AI_DIMENSIONS) {
    results.ai_feature_matrix.scores[competitor][dim] = null; // Claude 分析后填入
  }
}

// ── 保存结果 ──────────────────────────────────────────
const outputFile = path.join(outputDir, 'competitor_data.json');
fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));

const totalNews = Object.values(results.competitors).reduce((sum, c) => sum + (c.news?.length || 0), 0);
cliLog(`\n💾 已保存至 ${outputFile}`);
cliLog(`📊 总计: ${config.competitors.length} 个竞品, ${totalNews} 条资讯`);

await completeTaskSpace(taskName, { keep: false });
