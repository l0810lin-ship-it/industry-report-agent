/**
 * Agent 01 - 行业数据采集
 * 采集行业新闻、市场数据、平台动态
 * 运行方式: ego-browser nodejs < scripts/collect_industry.js
 */

const fs = require('fs');
const path = require('path');

const AGENT_DIR = process.env.AGENT_DIR || path.resolve(__dirname, '..');
const config = JSON.parse(fs.readFileSync(path.join(AGENT_DIR, 'config.json'), 'utf8'));
const outputDir = path.join(AGENT_DIR, 'output', 'raw');

if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

const { industry, company, year } = config.target;
const taskName = `collect-industry-${industry}-${year}`;
const task = await useOrCreateTaskSpace(taskName);

const results = { timestamp: new Date().toISOString(), industry, company, year, articles: [] };

// ── 36kr ──────────────────────────────────────────────
cliLog('📡 [1/4] 采集 36kr 行业资讯...');
try {
  const krUrl = `https://36kr.com/search/articles/${encodeURIComponent(industry + ' AI')}`;
  await openOrReuseTab(krUrl, { wait: true, timeout: 30 });
  await wait(3);

  const krItems = await js(String.raw`(() => {
    const cards = [...document.querySelectorAll('.article-item-title, .article-item, [class*="article"]')];
    return cards.slice(0, 15).map(el => ({
      title: el.querySelector('h3,h2,.title,a') ? (el.querySelector('h3,h2,.title,a').innerText || '').trim() : '',
      summary: el.querySelector('p,.desc,.summary') ? (el.querySelector('p,.desc,.summary').innerText || '').trim() : '',
      url: el.querySelector('a') ? el.querySelector('a').href : ''
    })).filter(item => item.title.length > 5);
  })()`);

  results.articles.push(...krItems.map(i => ({ ...i, source: '36kr' })));
  cliLog(`  ✅ 获取 ${krItems.length} 条`);
} catch (e) {
  cliLog(`  ⚠️ 36kr 采集异常: ${e.message}`);
}

// ── 虎嗅 ──────────────────────────────────────────────
cliLog('📡 [2/4] 采集虎嗅分析文章...');
try {
  const hxUrl = `https://www.huxiu.com/search.html?query=${encodeURIComponent(industry + ' AI 战略')}`;
  await openOrReuseTab(hxUrl, { wait: true, timeout: 30 });
  await wait(3);

  const hxItems = await js(String.raw`(() => {
    const items = [...document.querySelectorAll('.search-article-title, .article-title, h2, h3')];
    return items.slice(0, 12).map(el => ({
      title: el.innerText.trim(),
      url: el.closest('a') ? el.closest('a').href : (el.querySelector('a') ? el.querySelector('a').href : '')
    })).filter(i => i.title.length > 8 && !i.title.includes('搜索'));
  })()`);

  results.articles.push(...hxItems.map(i => ({ ...i, source: '虎嗅' })));
  cliLog(`  ✅ 获取 ${hxItems.length} 条`);
} catch (e) {
  cliLog(`  ⚠️ 虎嗅采集异常: ${e.message}`);
}

// ── 百度搜索（行业报告关键词）──────────────────────────
cliLog('📡 [3/4] 百度搜索行业关键词...');
const searchResults = {};
for (const keyword of config.research_keywords.slice(0, 3)) {
  try {
    await openOrReuseTab(`https://www.baidu.com/s?wd=${encodeURIComponent(keyword)}`, { wait: true, timeout: 20 });
    await wait(2);

    const baiduItems = await js(String.raw`(() => {
      const items = [...document.querySelectorAll('h3.t, .result h3, .c-title')];
      return items.slice(0, 8).map(el => ({
        title: el.innerText.trim(),
        url: el.querySelector('a') ? el.querySelector('a').href : ''
      })).filter(i => i.title.length > 5);
    })()`);

    searchResults[keyword] = baiduItems;
    cliLog(`  ✅ "${keyword}": ${baiduItems.length} 条`);
    await wait(1);
  } catch (e) {
    cliLog(`  ⚠️ "${keyword}" 搜索异常: ${e.message}`);
  }
}
results.search_results = searchResults;

// ── QuestMobile 免费报告摘要 ──────────────────────────
cliLog('📡 [4/4] 尝试采集 QuestMobile 摘要...');
try {
  await openOrReuseTab('https://www.questmobile.com.cn/research/report', { wait: true, timeout: 30 });
  await wait(3);

  const qmItems = await js(String.raw`(() => {
    const items = [...document.querySelectorAll('.report-item, .report-title, h3, .title')];
    return items.slice(0, 10).map(el => ({
      title: el.innerText.trim(),
      url: el.closest('a') ? el.closest('a').href : ''
    })).filter(i => i.title.length > 5);
  })()`);

  results.questmobile_reports = qmItems;
  cliLog(`  ✅ QuestMobile: ${qmItems.length} 条报告摘要`);
} catch (e) {
  cliLog(`  ⚠️ QuestMobile 采集跳过（可能需要登录）: ${e.message}`);
  results.questmobile_reports = [];
}

// ── 保存结果 ──────────────────────────────────────────
const outputFile = path.join(outputDir, 'industry_data.json');
fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
cliLog(`\n💾 已保存至 ${outputFile}`);
cliLog(`📊 总计采集: ${results.articles.length} 篇文章, ${Object.keys(results.search_results || {}).length} 个关键词搜索结果`);

await completeTaskSpace(taskName, { keep: false });
