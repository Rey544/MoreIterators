'use strict';
// UI strings only. Author text is explicitly excluded; no HTML or form values are rewritten.
window.MI18n = (() => {
  const storageKey = 'moreiterators.ui.language';
  const catalogs = {}, sourceKeys = new Map(), bindings = new Map(), missing = new Set(), renderedMessages = new Map();
  const attributes = ['title', 'alt', 'placeholder', 'aria-label', 'aria-description', 'aria-valuetext', 'label'];
  const protectedSelectors = '[data-i18n-content], [translate="no"], #subtitle, #pack-projects, .room-name';
  let patterns = [], locale = 'zh-CN', observer, changing = false;
  const normalizeLocale = value => /^en(?:-|$)/i.test(value || '') ? 'en' : /^zh(?:-|$)/i.test(value || '') ? 'zh-CN' : null;
  function chooseLocale() {
    const explicit = normalizeLocale(new URLSearchParams(location.search).get('lang'));
    let saved; try { saved = normalizeLocale(localStorage.getItem(storageKey)); } catch {}
    return explicit || saved || normalizeLocale(navigator.language) || 'zh-CN';
  }
  locale = chooseLocale();
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function record(key, source) {
    const item = source ? key + ': ' + source : key;
    if (!missing.has(item)) { missing.add(item); console.warn('[MI i18n] Missing UI string:', item); }
  }
  function format(key, params = {}, language = locale) {
    const value = catalogs[language]?.[key] ?? catalogs['zh-CN']?.[key];
    if (value === undefined) { if (catalogs['zh-CN']) record(key); return key; }
    return value.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (whole, name) => {
      if (!Object.hasOwn(params, name)) { record(key + '.' + name); return whole; }
      const item = params[name];
      return item && typeof item === 'object' && item.key ? format(item.key, item.params, language) : String(item ?? '');
    });
  }
  function t(key, params = {}) {
    const result = format(key, params);
    if (renderedMessages.size > 1000) renderedMessages.delete(renderedMessages.keys().next().value);
    renderedMessages.set(result, {key, params});
    return result;
  }
  function match(value, depth = 0) {
    if (depth > 8) return null;
    const trimmed = value.trim(), explicit = renderedMessages.get(trimmed), key = sourceKeys.get(trimmed);
    if (explicit) return {...explicit, before: '', after: ''};
    if (key) return {key, params: {}, before: value.slice(0, value.indexOf(trimmed)), after: value.slice(value.indexOf(trimmed) + trimmed.length)};
    for (const pattern of patterns) {
      const found = pattern.regex.exec(trimmed);
      if (!found) continue;
      const params = {};
      pattern.names.forEach((name, i) => {
        const raw = found[i + 1];
        // Only explicit UI-label parameters may resolve recursively. Author params stay byte-for-byte.
        const nested = pattern.uiParams.has(name) ? match(raw, depth + 1) : null;
        params[name] = nested ? {key: nested.key, params: nested.params} : raw;
      });
      return {key: pattern.key, params, before: value.slice(0, value.indexOf(trimmed)), after: value.slice(value.indexOf(trimmed) + trimmed.length)};
    }
    return null;
  }
  function text(value) {
    if (typeof value !== 'string') return value;
    const item = match(value);
    if (item) return item.before + format(item.key, item.params) + item.after;
    if (/[\u3400-\u9fff]/.test(value)) record('unmapped', value);
    return value;
  }
  function content(node) { node.setAttribute('data-i18n-content', ''); return node; }
  function isContent(node, attribute) {
    const element = node.nodeType === 3 ? node.parentElement : node;
    if (!element || element.closest(protectedSelectors)) return true;
    if (attribute && (element.getAttribute('data-i18n-content-attributes') || '').split(/\s+/).includes(attribute)) return true;
    if (!attribute && element.closest('script, style, textarea, [contenteditable="true"]')) return true;
    if (!attribute && element.tagName === 'OPTION') {
      const select = element.closest('select');
      if (select && ['projects', 'saved', 'candidate', 'readers', 'testProject', 'pool'].includes(select.id) && element.value !== '') return true;
    }
    return false;
  }
  function apply(node, attribute = null) {
    if (isContent(node, attribute)) return;
    const value = attribute ? node.getAttribute(attribute) : node.nodeValue;
    if (!value) return;
    let slots = bindings.get(node);
    const slot = attribute || '#text', previous = slots?.get(slot);
    if (previous && value === previous.rendered) return;
    const item = !attribute && node.parentElement?.tagName === 'OPTION' && value.trim() === '关闭'
      ? {key: 'common.off', params: {}, before: '', after: ''} : match(value);
    if (!item) {
      if (previous) slots.delete(slot);
      if (/[\u3400-\u9fff]/.test(value)) record('unmapped', value);
      return;
    }
    if (!slots) bindings.set(node, slots = new Map());
    const rendered = item.before + format(item.key, item.params) + item.after;
    slots.set(slot, {...item, rendered});
    if (value !== rendered) { if (attribute) node.setAttribute(attribute, rendered); else node.nodeValue = rendered; }
  }
  function scan(root) {
    if (root.nodeType === 3) { apply(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9) return;
    if (root.nodeType === 1) for (const name of attributes) if (root.hasAttribute(name)) apply(root, name);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeType === 3) apply(node);
      else for (const name of attributes) if (node.hasAttribute(name)) apply(node, name);
    }
  }
  function setLocale(value, persist = true) {
    const next = normalizeLocale(value) || 'zh-CN';
    if (!catalogs[next]) return;
    locale = next;
    if (persist) { try { localStorage.setItem(storageKey, locale); } catch {} }
    const url = new URL(location.href); url.searchParams.set('lang', locale); history.replaceState(null, '', url);
    document.documentElement.lang = locale;
    changing = true;
    for (const [node, slots] of bindings) {
      if (!node.isConnected) { bindings.delete(node); continue; }
      for (const [slot, item] of slots) {
        const attribute = slot === '#text' ? null : slot;
        if (isContent(node, attribute)) { slots.delete(slot); continue; }
        const current = attribute ? node.getAttribute(attribute) : node.nodeValue;
        if (current !== item.rendered) { apply(node, attribute); continue; }
        item.rendered = item.before + format(item.key, item.params) + item.after;
        if (attribute) node.setAttribute(attribute, item.rendered); else node.nodeValue = item.rendered;
      }
    }
    changing = false;
    document.querySelectorAll('[data-i18n-language]').forEach(select => select.value = locale);
    document.querySelectorAll('[data-language-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.languageChoice === locale)));
    // Links keep language across tabs; project/stage parameters remain intact.
    document.querySelectorAll('a[href]').forEach(link => {
      const target = new URL(link.href, location.href);
      if (target.origin === location.origin && ['/', '/dialogue', '/pearls', '/broadcasts', '/projections','/rooms'].includes(target.pathname)) { target.searchParams.set('lang', locale); link.href = target; }
    });
    window.dispatchEvent(new CustomEvent('mi-language-change', {detail: {locale}}));
  }
  function error(payload, fallback = '') {
    const known = payload?.error && match(payload.error);
    if (known) return t(known.key, known.params);
    if (payload?.code && catalogs['zh-CN']?.[payload.code]) return format(payload.code, payload.params || {});
    return text(payload?.error || fallback || format('common.request_failed'));
  }
  const ready = Promise.all(['zh-CN', 'en'].map(async language => {
    const response = await fetch('/locales/' + language + '.json');
    if (!response.ok) throw Error('Language resources: ' + response.status);
    catalogs[language] = await response.json();
  })).then(async () => {
    for (const dictionary of [catalogs['zh-CN'], catalogs.en]) for (const [key, value] of Object.entries(dictionary)) {
      const names = [...value.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)].map(item => item[1]);
      if (!names.length) { if (!sourceKeys.has(value)) sourceKeys.set(value, key); continue; }
      // Reject fully generic patterns; every template has a literal UI prefix/suffix.
      if (!/[A-Za-z\u3400-\u9fff]/.test(value.replace(/\{[^}]+\}/g, '')) && !key.startsWith('layer.order.')) continue;
      let cursor = 0, expression = '';
      for (const item of value.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)) {
        const numeric = /^(index|count|total|x|y|saturation|brightness|min|max|seconds|size)$/.test(item[1]);
        expression += escape(value.slice(cursor, item.index)) + (numeric ? '(-?\\d+(?:\\.\\d+)?)' : '([\\s\\S]*?)'); cursor = item.index + item[0].length;
      }
      expression += escape(value.slice(cursor));
      patterns.push({key, names, regex: new RegExp('^' + expression + '$'), weight: value.replace(/\{[^}]+\}/g, '').length, uiParams: new Set(['label', 'stage', 'part', 'side', 'action'])});
    }
    patterns.sort((a, b) => b.weight - a.weight);
    if (document.readyState === 'loading') {
      await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, {once: true}));
    }
    const select = document.createElement('select'); select.dataset.i18nLanguage = ''; select.setAttribute('aria-label', '界面语言');
    select.append(new Option('中文', 'zh-CN'), new Option('English', 'en')); select.value = locale;
    select.onchange = () => setLocale(select.value);
    select.hidden = true; select.tabIndex = -1; select.setAttribute('aria-hidden', 'true');
    const holder = document.createElement('div'); holder.className = 'mi-language-choice';
    const languageLabel = document.createElement('span'); languageLabel.textContent = '语言'; holder.append(languageLabel, select);
    for (const [value, name] of [['zh-CN', '中文'], ['en', 'English']]) {
      const button = content(document.createElement('button')); button.type = 'button'; button.textContent = name;
      button.dataset.languageChoice = value; button.setAttribute('aria-pressed', String(value === locale));
      button.onclick = () => setLocale(value); holder.append(button);
    }
    (document.querySelector('header') || document.body).append(holder);
    const diagnostics = document.createElement('button'); diagnostics.type = 'button'; diagnostics.textContent = '导出 log';
    holder.after(diagnostics);
    const dialog = document.createElement('dialog'), heading = document.createElement('h2'); heading.textContent = '导出 log';
    const state = document.createElement('p'), path = content(document.createElement('p')), list = content(document.createElement('pre'));
    const tail = content(document.createElement('pre')), actions = document.createElement('div'); actions.className = 'tools';
    dialog.className = 'mi-diagnostics'; dialog.append(heading, state, path, list, tail, actions);
    const download = document.createElement('button'), close = document.createElement('button');
    download.type = close.type = 'button'; download.textContent = '导出 log'; close.textContent = '关闭';
    actions.append(download, close); document.body.append(dialog); close.onclick = () => dialog.close();
    let logText = '';
    download.onclick = () => { const url = URL.createObjectURL(new Blob([logText], {type: 'text/plain;charset=utf-8'})), link = document.createElement('a'); link.href = url; link.download = 'LogOutput.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
    diagnostics.onclick = async () => {
      dialog.showModal(); state.textContent = '正在读取错误记录…'; path.textContent = list.textContent = tail.textContent = ''; download.disabled = true;
      try {
        const response = await fetch('/api/diagnostics'), result = await response.json();
        if (!response.ok) throw Error(error(result, response.statusText));
        state.textContent = result.available ? '日志尾部（可能不是完整日志）' : '尚未找到游戏日志';
        path.textContent = String(result.logPath || '') + (result.modified ? '\n' + result.modified : '');
        list.textContent = (result.errors || []).map(item => String(item.source || '') + '\n' + String(item.text || '')).join('\n\n');
        logText = String(result.tail || ''); tail.textContent = logText; download.disabled = !logText;
      } catch (failure) { state.textContent = text('读取错误记录失败：{detail}'.replace('{detail}', failure.message)); }
    };
    observer = new MutationObserver(records => {
      if (changing) return;
      for (const record of records) {
        if (record.type === 'characterData') apply(record.target);
        else if (record.type === 'attributes') apply(record.target, record.attributeName);
        else {
          record.removedNodes.forEach(root => {
            if (root.isConnected) return;
            bindings.delete(root);
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) bindings.delete(walker.currentNode);
          });
          record.addedNodes.forEach(scan);
        }
      }
    });
    scan(document); setLocale(locale, false);
    observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: attributes});
    window.addEventListener('storage', event => { if (event.key === storageKey) setLocale(event.newValue, false); });
    return locale;
  }).catch(error => { console.error('[MI i18n] Resources unavailable; Chinese UI retained.', error); return 'zh-CN'; });
  const confirmOriginal = window.confirm.bind(window), alertOriginal = window.alert.bind(window);
  window.confirm = value => confirmOriginal(text(String(value)));
  window.alert = value => alertOriginal(text(String(value)));
  return {ready, t, text, error, content, setLocale, get locale() { return locale; }, get missing() { return [...missing]; }, scan};
})();
