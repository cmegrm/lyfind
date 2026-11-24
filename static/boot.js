(function () {
  try {
    var theme = localStorage.getItem('lyfind-theme');
    if (theme !== 'dark' && theme !== 'light') theme = 'light';
    document.documentElement.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'dark' ? '#0b0b0c' : '#ffffff';
  } catch (err) {}
  var preferences = {};
  try { preferences = JSON.parse(localStorage.getItem('lyfind-accessibility')) || {}; } catch (err) {}
  document.documentElement.dataset.textSize = preferences.textSize === 'large' ? 'large' : 'normal';
  document.documentElement.dataset.contrast = preferences.contrast === 'high' ? 'high' : 'standard';
  document.documentElement.dataset.reducedMotion = String(preferences.motion === 'reduced' || window.matchMedia('(prefers-reduced-motion: reduce)').matches);
})();
