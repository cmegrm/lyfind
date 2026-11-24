'use strict';
let launchSetupKey=new URLSearchParams(location.hash.slice(1)).get('setup')||'';
let launchTesting = new URLSearchParams(location.hash.slice(1)).has('testing');
let launchTheme = launchTesting ? new URLSearchParams(location.hash.slice(1)).get('theme') : null;
if(launchSetupKey || launchTesting)history.replaceState(null,'',location.pathname+location.search);


// One short reveal per tab. Skip it when this tab has already opened LyFind, or when motion is reduced.
(function () {
  let play = false;
  try {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const seen = sessionStorage.getItem('lyfind-opened') === '1';
    play = !reduce && !seen;
    if (play) sessionStorage.setItem('lyfind-opened', '1');
  } catch (err) { /* private mode */ }
  document.documentElement.setAttribute('data-open', play ? 'play' : 'skip');
})();

// One icon set: 24px grid, 2px round line, currentColor. Sizes come from CSS (16 inline, 20 nav and buttons, 24 cards, 32 empty states).
const ICONS = {
  home: '<path d="M4 11 12 4l8 7"/><path d="M6 10v10h12V10"/><path d="M10 20v-6h4v6"/>',
  tasks: '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="m9 13 2 2 4-4"/>',
  match: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  inventory: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8"/><path d="M10 12h4"/>',
  shield: '<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3z"/><path d="m9 12 2 2 4-4"/>',
  settings: '<path d="M4 7h9M19 7h1M4 17h1M11 17h9"/><circle cx="16" cy="7" r="2.5"/><circle cx="8" cy="17" r="2.5"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 7 7 0 1 0 20 14.5z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.3a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2.2-2.5 3.8"/><path d="M12 17.2h.01"/>',
  notices: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 21h4"/>',
  logout: '<path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3"/><path d="m16 8 4 4-4 4M20 12H9"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  warning: '<path d="M10.3 4.3 2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 10v4M12 17h.01"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16h.01"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff: '<path d="m3 3 18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3 3.9M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a10 10 0 0 0 4.4-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  documents: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  id: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.5-1.5 1.7-2 3-2s2.5.5 3 2M15 10h3M15 14h3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
  accessibility: '<circle cx="12" cy="4" r="2"/><path d="M4 8l8 2 8-2M12 10v5M12 15l-5 6M12 15l5 6"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>',
  pencil: '<path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/><path d="m15 5 4 4"/>',
  bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6M10 22h4"/>',
  bag: '<path d="M6 8h12l1 12H5z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.3-9.3M17 6l3 3M14 9l2 2"/>',
  wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  electronics: '<rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18h2"/>',
  clothing: '<path d="M20.4 3.5 16 2a4 4 0 0 1-8 0L3.6 3.5a2 2 0 0 0-1.3 2.2l.6 3.5a1 1 0 0 0 1 .8H6v10a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V10h2.1a1 1 0 0 0 1-.8l.6-3.5a2 2 0 0 0-1.3-2.2z"/>',
  accessories: '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M11 3 8 9l4 12 4-12-3-6M2 9h20"/>'
};
// Older names still used by a few lists; they point at the same drawings.
ICONS.audit = ICONS.documents;
ICONS.overview = ICONS.home;
ICONS.cross = ICONS.close;
const OFFICE = {
  name: 'Center for Student Affairs (CSA)',
  place: 'LPU Cavite campus, Governor’s Drive, Brgy. Manggahan, General Trias — ask at Gate 1 or the Administration Building for the CSA office',
  hours: 'Mon to Fri, 8:00 AM to 5:00 PM',
  email: 'cav-csa@lpu.edu.ph',
  phone: '(046) 481-1414',
  phoneNote: 'Campus directory. Trunk (046) 481-1400 loc. 490. The CSA page also lists (046) 481-1490.'
};
const LOGO = '<img class="logo-img logo-light" src="/lyfind-logo.svg?v=244" alt="" width="40" height="40"><img class="logo-img logo-dark" src="/lyfind-logo-white.svg?v=244" alt="" width="40" height="40">';
const THEME_KEY = 'lyfind-theme';
function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
  } catch (err) { /* private mode */ }
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}
function applyTheme(theme) {
  const next = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = next === 'dark' ? '#0b0b0c' : '#ffffff';
  try { localStorage.setItem(THEME_KEY, next); } catch (err) { /* private mode */ }
  document.querySelectorAll('[data-action="set-theme"]').forEach(btn => {
    btn.setAttribute('aria-pressed', String(btn.dataset.theme === next));
  });
  document.querySelectorAll('[data-action="toggle-theme"]').forEach(updateThemeButton);
}
function updateThemeButton(button) {
  const dark = document.documentElement.dataset.theme === 'dark';
  const label = dark ? 'Switch to light mode' : 'Switch to dark mode';
  button.innerHTML = svg(dark ? 'sun' : 'moon');
  button.setAttribute('aria-label', label);
  button.title = label;
}
function syncQuickTools() {
  const tools = document.querySelector('#quick-tools');
  if (!tools) return;
  if (!tools.querySelector('[data-action="toggle-theme"]')) {
    tools.innerHTML = '<button type="button" class="quick-control" data-action="toggle-theme"></button><button type="button" class="quick-control" data-action="open-accessibility" aria-label="Accessibility settings" title="Accessibility" aria-haspopup="dialog" aria-controls="accessibility"></button><button type="button" class="quick-control" data-action="quick-testing" aria-label="Open testing" title="Testing" aria-haspopup="dialog" hidden></button>';
    updateThemeButton(tools.firstElementChild);
    tools.querySelector('[data-action="open-accessibility"]').innerHTML = svg('accessibility');
    tools.lastElementChild.innerHTML = svg('more');
  }
  tools.querySelector('[data-action="quick-testing"]').hidden = !(state.config.demo_mode || state.config.testing_available);
}
function syncDialogTheme() {
  // Keep theme and accessibility controls strictly in the bottom-right quick bar.
}
// The only icon helper. Decorative by default (aria-hidden). Size is set by CSS for each place it is used.
function svg(name) {
  return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONS[name] || ICONS.inventory}</svg>`;
}
const CATEGORY_GROUPS = [
  ['Everyday', [
    ['id', 'School ID'], ['phone', 'Phone'], ['wallets', 'Wallets'], ['keys', 'Keys'],
    ['cards', 'Cards'], ['cash', 'Cash'], ['watch', 'Watch'], ['glasses', 'Glasses'], ['jewelry', 'Jewelry']
  ]],
  ['Bags and clothes', [
    ['bags', 'Bags'], ['clothing', 'Clothing'], ['shoes', 'Shoes'], ['uniform', 'Uniform'], ['accessories', 'Accessories']
  ]],
  ['Devices', [
    ['laptop', 'Laptop'], ['earphones', 'Earphones'], ['charger', 'Charger or cable'],
    ['usb', 'USB drive'], ['calculator', 'Calculator'], ['electronics', 'Electronics']
  ]],
  ['School and other', [
    ['books', 'Books or notebooks'], ['documents', 'Documents'], ['umbrella', 'Umbrella'],
    ['bottle', 'Bottle or tumbler'], ['sports', 'Sports gear'], ['medicine', 'Medicine'], ['other', 'Other']
  ]]
];
const CATEGORIES = CATEGORY_GROUPS.flatMap(group => group[1]);
const PLACE_GROUPS = [
  ['Buildings', [
    'Jose P. Laurel (JPL) Building', 'Sotero H. Laurel (SHL) Building', 'East Building', 'West Building',
    'Academic Resource Center (Library)', 'COECSA Building', 'L Building (beside COECSA)'
  ]],
  ['Inside COECSA', [
    'COECSA lobby', 'COECSA canteen, ground floor', 'CEA faculty, COECSA 2nd floor',
    'CCS rooms and faculty, COECSA 6th floor', 'COECSA Student Lounge, 10th floor'
  ]],
  ['Around campus', [
    'Chapel of the Sacred Heart of Jesus', 'University Auditorium', 'Student Center (East Building)',
    'Bookstore (East Building)', 'Le Café (SHL, ground floor)', 'Lemongrass (West Building)',
    'JPL rooftop canteen', 'Coffee shop (Academic Resource Center)', 'Gymnasium', 'Covered court',
    'Freedom Park', 'Gate 1', 'Gate 2', 'CSA Office', 'Campus parking', 'Other'
  ]]
];
const PLACES = PLACE_GROUPS.flatMap(group => group[1]);
const TIMES = ['Morning', 'Lunch time', 'Afternoon', 'Evening', 'Not sure'];
const WHERE_NOW = [['with_me', 'I have it with me'], ['security', 'I gave it to campus security'], ['left', 'I left it where I found it']];
// One example and one "what makes it yours" hint per kind of item. The form swaps them in when the kind changes.
const CATEGORY_TIPS = {
  id: ['a school ID in a clear case', 'The photo, a sticker, or a crack. Do not type the ID number.'],
  phone: ['a black phone with a cracked corner and a clear case', 'Stickers, cracks, or the lock-screen picture. Do not type a password.'],
  wallets: ['a brown leather wallet with a zipper', 'The lining color or the kinds of cards inside. Do not type card numbers.'],
  keys: ['three keys on a ring with a yellow tag', 'How many keys, the keychain, or any labels.'],
  cards: ['a campus card in a plastic sleeve', 'The color of the sleeve. Do not type the card number.'],
  cash: ['a folded bill inside a small envelope', 'The envelope or a clip. Do not write the amount here if you would rather tell CSA in person.'],
  watch: ['a silver watch with a black strap', 'Engraving, the face, or a scratch.'],
  glasses: ['black eyeglasses in a hard case', 'The case, a missing nose pad, or a crack.'],
  jewelry: ['a thin gold necklace with a small pendant', 'The pendant shape or a clasp mark.'],
  bags: ['a dark green backpack with a front pocket', 'A keychain, patches, a name tag, or what is inside.'],
  clothing: ['a gray hoodie with a white logo', 'Size, tags, stains, or initials.'],
  shoes: ['black rubber shoes with a white sole', 'The size, wear on the sole, or a name inside.'],
  uniform: ['a white school polo with a name tape', 'The tape, a stain, or the size. Do not type the full name if it is private.'],
  accessories: ['a maroon hair clip with a small bow', 'The color, a chip, or what it was attached to.'],
  laptop: ['a silver laptop with a sticker on the lid', 'The sticker, a dent, or the desktop picture. Do not type a password.'],
  earphones: ['white wired earphones in a small pouch', 'The pouch, a bent wire, or one missing tip.'],
  charger: ['a white charging cable with a frayed end', 'The plug type, a knot, or a mark on the brick.'],
  usb: ['a black USB drive on a key ring', 'The cap, a label, or the key ring.'],
  calculator: ['a black scientific calculator', 'A name written inside the cover, or a missing key.'],
  electronics: ['a black power bank with a worn corner', 'Stickers, cracks, or a label.'],
  books: ['a blue notebook with a torn cover', 'Writing on the cover, or a bookmark. Do not type homework answers.'],
  documents: ['a blue folder with printed forms', 'The type of document. Do not type ID numbers here.'],
  umbrella: ['a black umbrella with a wooden handle', 'A broken rib, a tag, or the handle color.'],
  bottle: ['a green tumbler with a straw lid', 'Stickers, a dent, or a name on the bottom.'],
  sports: ['a badminton racket in a black cover', 'The grip tape, a string, or a mark on the frame.'],
  medicine: ['a small labeled medicine pouch', 'The pouch color. Do not type the medicine name if it is private.'],
  other: ['a black umbrella with a wooden handle', 'Anything that makes it different from the same item.']
};
const COLORS = ['Black', 'Blue', 'Brown', 'Gray', 'Green', 'Orange', 'Pink', 'Purple', 'Red', 'White', 'Yellow', 'Gold', 'Silver', 'Multicolor'];
const CATEGORY_ICON = {
  electronics: 'electronics', bags: 'bag', wallets: 'wallet', keys: 'key', documents: 'documents', clothing: 'clothing', accessories: 'accessories', other: 'inventory',
  id: 'id', phone: 'phone', laptop: 'electronics', charger: 'electronics', earphones: 'electronics', usb: 'electronics', calculator: 'electronics',
  umbrella: 'inventory', bottle: 'inventory', books: 'documents', glasses: 'accessories', jewelry: 'accessories', shoes: 'clothing', watch: 'clock',
  cash: 'wallet', cards: 'id', uniform: 'clothing', sports: 'inventory', medicine: 'inventory'
};
const FALLBACK_LABELS = {
  available: 'In the office', under_verification: 'Being checked', released: 'Handed back', unclaimed: 'Holding period ended',
  step1_pending: 'Under review', step2_pending: 'Office visit next', verified: 'Ready to approve',
  approved: 'Ready to hand over', rejected: 'Not approved', awaiting_turn_in: 'Bring it to the office', received: 'Received at the office',
  suggested: 'Needs a decision', confirmed: 'Waiting for the owner', dismissed: 'Not a match', open: 'Still looking', closed: 'Closed',
  active: 'Active', inactive: 'Inactive'
};
const TONE = {
  released: 'good', closed: 'good', received: 'good', active: 'good', available: 'good',
  verified: 'ready', approved: 'ready', confirmed: 'ready',
  rejected: 'bad', dismissed: 'bad', unclaimed: 'bad', inactive: 'bad'
};
const STAGES = ['Reported', 'Matched', 'Verified', 'Released'];
const PAGE_SIZE = 6;

const state = {
  config: {}, user: null, data: {}, view: 'home', screen: 'welcome', authMode: 'signin', signupKind: 'lpu', csrf: '',
  query: '', category: '', page: {}, tab: { desk: 'all', items: 'office', office: 'staff', reports: 'lost', claims: 'needs', matches: 'review', lost: 'need', mine: 'open', myclaims: 'invites' },
  intent: null, quick: null, taskKey: null, focusId: null, authBusy: false, pending: null
};
const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
const mobileLayout = window.matchMedia('(max-width: 960px)');
const appDrawerLayout = window.matchMedia('(max-width: 1080px)');
let toastTimer, searchTimer, progressTimer, modalClosing = false;
const fileUrls = new Set();

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const arr = key => Array.isArray(state.data[key]) ? state.data[key] : [];
const admin = () => state.user?.role === 'admin';
const catName = value => CATEGORIES.find(([key]) => key === value)?.[1] || 'Item';
const catIcon = value => svg(CATEGORY_ICON[value] || 'inventory');
const firstName = name => String(name || 'the owner').trim().split(/\s+/)[0];
const today = () => new Date().toLocaleDateString('en-CA');
function earliestReportDay() {
  const now = new Date();
  const monthIndex = now.getMonth() - 3;
  const probe = new Date(now.getFullYear(), monthIndex, 1);
  const last = new Date(probe.getFullYear(), probe.getMonth() + 1, 0).getDate();
  return new Date(probe.getFullYear(), probe.getMonth(), Math.min(now.getDate(), last)).toLocaleDateString('en-CA');
}
function dateProblem(value) {
  if (!value) return 'Choose a date.';
  if (value > today()) return 'That date is still in the future. Choose today or an earlier day.';
  if (value < earliestReportDay()) return 'That date is more than 3 months ago. Choose a more recent day.';
  return '';
}
const REPORT_DATE_NOTE = '<p class="note" role="note">A future date is blocked. A date more than 3 months ago cannot be filed.</p>';
function parseDay(value) {
  if (!value) return null;
  const raw = String(value);
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(raw)
    ? new Date(...raw.split('-').map((part, index) => Number(part) - (index === 1 ? 1 : 0)))
    : new Date(raw.includes('T') ? raw : raw.replace(' ', 'T') + 'Z');
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
function dayKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
function dateInfo(value) {
  const parsed = parseDay(value);
  if (!parsed) return null;
  const now = new Date();
  const key = dayKey(parsed);
  const relative = key === dayKey(now) ? 'Today' : key === dayKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)) ? 'Yesterday' : '';
  const weekday = parsed.toLocaleDateString('en-US', { weekday: 'short' });
  const shortDate = parsed.toLocaleDateString('en-US', parsed.getFullYear() === now.getFullYear()
    ? { month: 'short', day: 'numeric' } : { month: 'short', day: 'numeric', year: 'numeric' });
  return { relative, weekday, shortDate };
}
function dateText(value) {
  const info = dateInfo(value);
  if (!info) return '';
  const core = `${info.weekday}, ${info.shortDate}`;
  return info.relative ? `${info.relative} · ${core}` : core;
}
function dateLine(value, kind) {
  const info = dateInfo(value);
  if (!info) return `<p class="date-line"><span class="date-kind">${esc(kind)}</span><span class="date-when">Date not set</span></p>`;
  const rel = info.relative ? `<span class="date-rel">${esc(info.relative)}</span>` : '';
  return `<p class="date-line"><span class="date-kind">${esc(kind)}</span>${rel}<span class="date-when">${esc(info.weekday)}, ${esc(info.shortDate)}</span></p>`;
}
function statusMarkup(message, kind) {
  const icon = kind === 'error' ? 'cross' : kind === 'wait' ? 'clock' : 'check';
  return `<span class="status-icon" aria-hidden="true">${svg(icon)}</span><span class="status-text">${esc(message)}</span>`;
}
function toast(message, tone) {
  const el = document.querySelector('#toast');
  const kind = tone === true || tone === 'error' ? 'error' : tone === 'wait' ? 'wait' : 'ok';
  el.innerHTML = statusMarkup(message, kind);
  el.className = `toast visible ${kind}`;
  el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  el.setAttribute('aria-live', kind === 'error' ? 'assertive' : 'polite');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, message.length > 80 ? 9000 : 6000);
}
function savedRefreshNotice() {
  clearTimeout(toastTimer);
  const notice=document.querySelector('#toast');
  notice.innerHTML=`${statusMarkup('Saved. The dashboard could not refresh. Your change does not need to be submitted again.','wait')}<button type="button" class="btn secondary sm" data-action="retry-dashboard">Refresh dashboard</button>`;
  notice.className='toast visible retry-toast';
  notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
}
let pending = 0;
async function api(path, data) {
  const options = { credentials: 'same-origin', headers: {} };
  if (data !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.headers['X-CSRF-Token'] = state.csrf;
    options.body = JSON.stringify(data);
  }
  pending += 1;
  document.body.classList.add('network-busy');
  document.body.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(path, options);
    let result;
    try { result = await response.json(); }
    catch { const error = new Error('The server sent an unexpected reply. Try again.'); error.retryable = true; throw error; }
    if (!response.ok || !result.ok) {
      if (response.status === 401 && state.user && !path.startsWith('/api/auth/')) {
        if (modal.open) closeModal();
        resetSession();
        state.screen = 'auth';
        queueMicrotask(() => boot());
      }
      const failure = new Error(result.error || 'This could not be saved. Try again.');
      failure.fields = result.fields || null;
      failure.status = response.status;
      failure.retryable = response.status >= 500;
      throw failure;
    }
    return result.data;
  } catch (error) {
    if (error instanceof TypeError) {
      const failure = new Error('Could not reach LyFind. Check your connection and try again.');
      failure.retryable = true;
      throw failure;
    }
    throw error;
  } finally {
    pending -= 1;
    if (pending === 0) {
      document.body.classList.remove('network-busy');
      document.body.classList.add('network-done');
      document.body.setAttribute('aria-busy', 'false');
      clearTimeout(progressTimer);
      progressTimer = setTimeout(() => document.body.classList.remove('network-done'), 400);
    }
  }
}
async function load() {
  state.data = await api('/api/dashboard');
  if (state.data.user) state.user = state.data.user;
  render();
  if (state.intent && !admin()) {
    const intent = state.intent;
    state.intent = null;
    if (intent === 'lost') lostForm();
    else if (intent === 'found' && state.user.role !== 'guest') foundForm();
    else if (intent === 'claims') { state.view = 'claims'; render(); }
  }
}
async function boot() {
  applyTheme(launchTheme === 'dark' || launchTheme === 'light' ? launchTheme : readTheme());
  launchTheme = null;
  try {
    state.config = await api('/api/config');
    state.csrf = state.config.csrf_token || '';
    const session = await api('/api/session');
    state.csrf = session.csrf_token || state.csrf;
    state.user = session.user;
    if (state.user) await load();
    else render();
    if (launchTesting && state.config.demo_mode) { launchTesting = false; quickTesting(); }
  } catch (error) {
    app.innerHTML = `<div class="loading-screen"><h1>LyFind did not open</h1><p>${esc(error.message)}</p><button class="btn primary" type="button" data-action="reload">Try again</button></div>`;
  }
  syncQuickTools();
}

function navGroups() {
  const notes = ['updates', 'Notifications', 'notices'];
  const account = ['account', 'Account', 'user'];
  if (admin()) return [
    ['', [['today', 'Dashboard', 'tasks'], ['lost', 'Lost reports', 'documents'], ['items', 'Found items', 'inventory'], ['matches', 'Matches', 'match'], ['claims', 'Claims', 'shield'], notes, ['office', 'Administration', 'settings']]],
    ['', [account]]
  ];
  return [
    ['', [['home', 'Dashboard', 'home'], ...(state.user.role!=='guest'?[['board','Found items','inventory']]:[]), ['reports', 'My reports', 'documents'], ['claims', 'My claims', 'shield'], notes]],
    ['', [account]]
  ];
}
function navItems() {
  return navGroups().flatMap(group => group[1]);
}
function navOn(key) {
  return state.view === key;
}
function navCounts() {
  const notes = admin() ? staffInbox().length : arr('notifications').length;
  if (!admin()) {
    const mine = arr('claims').filter(claim => !['released', 'rejected'].includes(claim.status)).length;
    return { claims: mine, updates: notes };
  }
  const desk = deskCounts();
  return { lost: desk.need, items: desk.arriving, matches: desk.review, claims: desk.claims, updates: notes };
}
function deskCounts() {
  const need = arr('reports').filter(report => lostWork(report) === 'need').length;
  const arriving = arr('found_reports').filter(report => report.status === 'awaiting_turn_in' && !report.hidden).length;
  const review = arr('matches').filter(match => match.status === 'suggested').length;
  const claims = waitingClaims().length;
  return { need, arriving, review, claims, total: need + arriving + review + claims };
}
function deskSteps(active) {
  const n = deskCounts();
  const step = (view, number, title, count, text) => `<button class="queue-line desk-step${active === view ? ' on' : ''}" type="button" data-nav="${view}" ${active === view ? 'aria-current="step"' : ''}><span class="step-no" aria-hidden="true">${number}</span><span class="grow"><strong>${title}</strong><span>${count ? `${count} ${text}` : 'Nothing waiting'}</span></span></button>`;
  const steps = step('lost', 1, 'Lost reports', n.need, 'awaiting action') + step('items', 2, 'Found items', n.arriving, 'awaiting arrival') + step('matches', 3, 'Matches', n.review, 'awaiting review') + step('claims', 4, 'Claims', n.claims, 'awaiting review');
  return `<div class="desk-rail"><nav class="desk-steps" aria-label="Desk pages">${steps}</nav><div class="desk-dots" hidden aria-hidden="true"><i></i><i></i><i></i><i></i></div></div>`;
}
// Most urgent first: claims closest to finished, then the ones that have waited longest.
const URGENCY = { approved: 0, verified: 1, step2_pending: 2, step1_pending: 3 };
function waitingClaims() {
  return arr('claims').filter(claim => claim.status in URGENCY).sort((a, b) => URGENCY[a.status] - URGENCY[b.status] || Number(a.id) - Number(b.id));
}
function doneThisWeek() {
  return arr('claims').filter(claim => claim.status === 'released' && daysAgo(claim.released_at) <= 7).sort((a, b) => String(b.released_at).localeCompare(String(a.released_at)));
}
const QUICK = {
  waiting: { view: 'claims', title: 'Waiting claims', text: 'Claims that still need a check. The ones closest to pickup are listed first.' },
  matches: { view: 'matches', title: 'Matches to review', text: 'Strongest matches first. Approve one to invite the owner.' },
  office: { view: 'items', title: 'In the office', text: 'Items at the CSA office, oldest first.' },
  done: { view: 'claims', title: 'Done this week', text: 'Items handed back in the last 7 days.' }
};
function filterChip(label, count, noun) {
  return `<div class="filter-row"><span class="chip">${svg('check')}<span>Showing: <b>${esc(label)}</b></span><button class="chip-clear" type="button" data-action="clear-quick" aria-label="Clear filter: ${esc(label)}">${svg('close')}<span>Clear</span></button></span><span class="meta">${count} ${noun}${count === 1 ? '' : 's'}</span></div>`;
}
function openQuick(kind) {
  const quick = QUICK[kind];
  if (!quick) return;
  state.view = quick.view;
  state.quick = kind;
  state.query = '';
  state.page = {};
  state.filter = kind === 'office' ? 'available' : '';
  state.category = '';
  if (kind === 'office') state.tab.items = 'office';
  if (kind === 'matches') state.tab.matches = 'review';
  if (kind === 'waiting') state.tab.claims = 'needs';
  closeMenu(false);
  render();
  window.scrollTo(0, 0);
  document.querySelector('.main h1')?.focus();
}
function clearQuick() {
  const was = state.quick;
  state.quick = null;
  state.page = {};
  if (state.view === 'items' || was === 'office') state.filter = '';
  if (was === 'waiting') state.tab.claims = 'needs';
  if (was === 'done') state.tab.claims = 'finished';
  if (was === 'matches') state.tab.matches = 'review';
  render();
  document.querySelector('.main h1')?.focus();
}
function roleLabel(role) {
  return { guest: 'Guest', student: 'Student', professor: 'Professor', admin: 'Staff' }[role] || '';
}
function badge(row) {
  const text = row.status_label || FALLBACK_LABELS[row.status] || 'Update';
  const tone = TONE[row.status] || 'wait';
  const icon = tone === 'bad' ? 'warning' : tone === 'good' || tone === 'ready' ? 'check' : 'clock';
  return `<span class="badge ${tone}">${svg(icon)}<span>${esc(text)}</span></span>`;
}
function trackerModel(source) {
  const claim = source.claim;
  if (claim?.status === 'rejected') {
    return { states: ['done', 'done', 'stopped', 'later'], line: claim.reason ? `Not approved. ${claim.reason}` : 'Not approved. Read the reason, then ask CSA if you can try again.' };
  }
  if (claim?.status === 'released') {
    const when = dateText(claim.released_at);
    return { states: ['done', 'done', 'done', 'done'], line: `Done. This item was handed back${when ? ` on ${when}` : ''}.` };
  }
  let now = 0;
  let line = 'Press Report lost to start.';
  if (claim) {
    if (claim.status === 'approved') { now = 3; line = 'Approved. Bring your ID to the CSA office to pick it up.'; }
    else if (claim.status === 'verified') { now = 3; line = 'Both checks passed. CSA will approve the handover.'; }
    else if (claim.status === 'step2_pending') { now = 2; line = 'Bring your ID to the CSA office.'; }
    else { now = 2; line = 'CSA is reading the answers.'; }
  } else if (source.invite) {
    now = 1;
    line = source.invite.can_claim === false ? (source.invite.eligibility_note || 'This invitation is not open right now.') : 'CSA invited you. Answer a few questions.';
  } else if (source.report) {
    now = source.report.status === 'closed' ? 4 : 0;
    line = source.report.status === 'closed' ? 'This report is closed.' : 'CSA is looking for a match. We will notify you.';
  }
  const states = STAGES.map((_, index) => (index < now ? 'done' : index === now ? 'now' : 'later'));
  return { states, line };
}
function tracker(source, compact, fit) {
  const model = trackerModel(source);
  const items = STAGES.map((name, index) => {
    const mode = model.states[index];
    const mark = mode === 'done' ? svg('check') : mode === 'stopped' ? svg('alert') : String(index + 1);
    return `<li class="${mode}"><span class="step-name"><span class="mark">${mark}</span><span>${name}</span></span></li>`;
  }).join('');
  return `<ol class="tracker${compact ? ' compact' : ''}${fit ? ' fit' : ''}" aria-label="Where this item is in the process">${items}</ol>${compact ? '' : `<p class="next-line">${esc(model.line)}</p>`}`;
}
function journey() {
  const claims = arr('claims');
  const active = claims.find(claim => !['released', 'rejected'].includes(claim.status));
  if (active) return { claim: active, report: { description: active.report_description || active.item_description, status: 'open' } };
  const invite = arr('matches').find(match => match.status === 'confirmed');
  if (invite) return { invite, report: { description: invite.report_description, status: 'open' } };
  const open = arr('reports').find(report => report.status === 'open');
  if (open) return { report: open };
  const done = claims.find(claim => claim.status === 'released');
  if (done) return { claim: done, report: { description: done.report_description || done.item_description, status: 'closed' } };
  const any = arr('reports')[0];
  return any ? { report: any } : {};
}
function journeyTitle(source) {
  return source.report?.description || source.claim?.report_description || source.invite?.report_description || '';
}
function sourceForReport(report) {
  const related = arr('claims').filter(claim => String(claim.report_id) === String(report.id));
  const claim = related.find(item => item.status !== 'rejected') || related[0];
  const invite = arr('matches').find(match => String(match.report_id) === String(report.id) && match.status === 'confirmed');
  return { report, claim, invite };
}
function button(label, action, id, kind) {
  if(action==='found' && state.user?.role==='guest')return '';
  return `<button class="btn ${kind || ''}" type="button" data-action="${esc(action)}" data-id="${esc(id || '')}">${label}</button>`;
}
function disabledButton(label, why) {
  return `<span class="action-lock"><button class="btn" type="button" disabled title="${esc(why)}">${label}</button><span class="why">${esc(why)}</span></span>`;
}
const ACTIVE_CLAIM = ['step1_pending', 'step2_pending', 'verified', 'approved'];
const STAFF_STEPS = ['Report', 'Match', 'Verify', 'Hand over', 'Done'];
function moreMenu(entries) {
  return `<details class="more"><summary class="btn secondary sm icon-only" title="More actions" aria-label="More actions">${svg('more')}</summary><div class="more-menu">${entries.map(([label, action, id, danger]) => `<button class="menu-item${danger ? ' danger' : ''}" type="button" data-action="${esc(action)}" data-id="${esc(id || '')}">${label}</button>`).join('')}</div></details>`;
}
function placeMoreMenu(menu) {
  const panel = menu.querySelector('.more-menu');
  const button = menu.querySelector('summary');
  if (!panel || !button) return;
  if (!menu.open) { panel.style.cssText = ''; return; }
  const rail = menu.closest('.card-rail, .table-wrap, .desk-scroll');
  const rect = button.getBoundingClientRect();
  if (rail) {
    const box = rail.getBoundingClientRect();
    if (rect.bottom < box.top + 4 || rect.top > box.bottom - 4) { menu.open = false; return; }
  }
  panel.style.cssText = 'position:fixed;right:auto;bottom:auto;margin:0;visibility:hidden;display:grid;';
  const gap = 6;
  const edge = 8;
  const width = panel.offsetWidth;
  const height = panel.offsetHeight;
  const card = menu.closest('article');
  const next = card?.nextElementSibling;
  const nextTop = next ? next.getBoundingClientRect().top : window.innerHeight;
  const fitsBelow = rect.bottom + gap + height <= Math.min(window.innerHeight - edge, nextTop - gap);
  const top = fitsBelow
    ? rect.bottom + gap
    : Math.max(edge, rect.top - gap - height);
  let left = rect.left;
  if (left + width > window.innerWidth - edge) left = rect.right - width;
  left = Math.max(edge, Math.min(left, window.innerWidth - edge - width));
  panel.style.top = `${top}px`;
  panel.style.left = `${left}px`;
  panel.style.zIndex = '80';
  panel.style.visibility = 'visible';
}
function staffSteps(stage, compact) {
  const items = STAFF_STEPS.map((name, index) => {
    const mode = stage.done || index < stage.index ? 'done' : index === stage.index ? (stage.stopped ? 'stopped' : 'now') : 'later';
    const mark = mode === 'done' ? svg('check') : mode === 'stopped' ? svg('alert') : String(index + 1);
    return `<li class="${mode}"${mode === 'now' || mode === 'stopped' ? ' aria-current="step"' : ''}><span class="step-name"><span class="mark">${mark}</span><span>${name}</span></span></li>`;
  }).join('');
  const where = stage.done ? 'All steps done' : `Step ${stage.index + 1} of 5: ${STAFF_STEPS[stage.index]}${stage.stopped ? ' (stopped)' : ''}`;
  return `<ol class="tracker five${compact ? ' compact' : ''}" aria-label="${where}">${items}</ol>`;
}
function claimStage(claim) {
  if (claim.status === 'released') return { index: 4, done: true };
  if (claim.status === 'rejected') return { index: 2, stopped: true };
  if (claim.status === 'verified' || claim.status === 'approved') return { index: 3 };
  return { index: 2 };
}
function matchesFor(key, id) {
  return arr('matches').filter(match => String(match[key]) === String(id));
}
function reportStage(report) {
  if (report.status === 'closed') return { index: 4, done: true };
  const claim = arr('claims').find(item => String(item.report_id) === String(report.id) && item.status !== 'rejected');
  if (claim) return claimStage(claim);
  const found = matchesFor('report_id', report.id);
  if (found.some(match => match.status === 'confirmed')) return { index: 2 };
  if (found.some(match => match.status === 'suggested')) return { index: 1 };
  return { index: 0 };
}
function itemStage(item) {
  if (item.status === 'released') return { index: 4, done: true };
  const claim = arr('claims').find(entry => String(entry.item_id) === String(item.id) && ACTIVE_CLAIM.includes(entry.status));
  if (claim) return claimStage(claim);
  const found = matchesFor('item_id', item.id);
  if (found.some(match => match.status === 'confirmed')) return { index: 2 };
  if (found.some(match => match.status === 'suggested')) return { index: 1 };
  return { index: 0 };
}
function stepText(stage) {
  return stage.done ? 'Done' : `Step ${stage.index + 1} of 5: ${STAFF_STEPS[stage.index]}`;
}
function nextForClaim(claim) {
  const consented = Boolean(claim.consent_at || claim.in_person_consent);
  return {
    step1_pending: 'Read the answers and compare them with the private details. Then pass the online check, or reject the claim.',
    step2_pending: consented ? 'Check the owner’s ID and answers in person. Then pass the office check, or reject the claim.' : 'When the owner is at the office, press Start office check.',
    verified: 'Add the three photos, then press Approve handover.',
    approved: 'Give the item to the owner, then press Hand over item.',
    released: 'Done. The report is closed.',
    rejected: 'Rejected. The owner can read the reason.'
  }[claim.status] || '';
}
function staffClaimActions(claim) {
  const more = [];
  let primary = '';
  if (claim.status === 'step1_pending') { primary = button('Pass online check', 'online-pass', claim.id, 'primary'); more.push(['Reject', 'online-reject', claim.id, true]); }
  else if (claim.status === 'step2_pending') {
    const consented = Boolean(claim.consent_at || claim.in_person_consent);
    primary = consented ? button('Pass office check', 'inperson-pass', claim.id, 'primary') : button('Start office check', 'consent', claim.id, 'primary');
    more.push(['Reject', 'inperson-reject', claim.id, true]);
  } else if (claim.status === 'verified') primary = button('Approve handover', 'approve', claim.id, 'primary');
  else if (claim.status === 'approved') primary = button('Hand over item', 'release', claim.id, 'primary');
  more.push(['View item', 'view-item', claim.item_id]);
  return primary + moreMenu(more);
}
function answersText(claim) {
  if (claim.answers && typeof claim.answers === 'object') {
    return Object.entries(claim.answers).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join('\n');
  }
  return claim.answers || 'No answers yet.';
}
function claimTitle(claim) {
  return admin() ? (claim.item_description || 'Item at the office') : (claim.report_description || claim.item_description || 'Your item');
}
function claimCard(claim) {
  const title = claimTitle(claim);
  const staff = admin();
  const photo = staff && claim.item_photo_id
    ? `<img class="thumb" alt="Photo of the item, visible to staff only" src="/api/files/${encodeURIComponent(claim.item_photo_id)}">`
    : `<span class="item-icon" aria-hidden="true">${catIcon(claim.item_category)}</span>`;
  const reach = staff && claim.claimant_phone ? `<p class="meta">Phone ${esc(claim.claimant_phone)}</p>` : '';
  const who = staff ? `${esc(claim.claimant_name || 'Owner')}${claim.claimant_student_number ? ` (${esc(claim.claimant_student_number)})` : ''} · ${esc(catName(claim.item_category))}` : esc(catName(claim.item_category));
  const focused = state.taskKey === `claim:${claim.id}` ? ' is-focus' : '';
  return `<article class="claim${focused}" data-claim="${esc(claim.id)}" id="claim-${esc(claim.id)}">
    <div class="status-corner">${badge(claim)}</div>
    <div class="claim-main">${photo}<div class="report-copy"><h3>${esc(title)}</h3><p class="meta">${who}</p>${reach}</div></div>
    <div class="claim-progress">${staff ? staffSteps(claimStage(claim), true) : tracker({ claim })}</div>
    ${staff ? `<p class="next-step"><b>Next:</b> ${esc(nextForClaim(claim))}</p>` : ''}
    ${claim.reason ? `<div class="private-box"><span class="kicker">What happened</span><p>${esc(claim.reason)}</p></div>` : ''}
    ${staff ? `<div class="answer-block"><p class="kicker">Ownership answers</p><p class="answers">${esc(answersText(claim))}</p></div>` : ''}
    ${claim.consent_at ? `<p class="meta">Office check started ${esc(dateText(claim.consent_at))}.</p>` : ''}
    ${(() => {
      const passReady = ['step2_pending', 'verified', 'approved', 'released'].includes(claim.status);
      const passBtn = passReady ? button(claim.status === 'released' ? 'Handover receipt' : 'View Claim Pass', 'claim-pass', claim.id, claim.status === 'approved' ? 'primary sm' : 'secondary sm') : '';
      const staffBtns = staff ? staffClaimActions(claim) : '';
      return staffBtns || passBtn ? `<div class="claim-actions">${staffBtns}${passBtn}</div>` : '';
    })()}
  </article>`;
}
function srHeading(text) {
  return `<h2 class="sr-only">${esc(text)}</h2>`;
}
function pageHead(title, text, actions) {
  return `<header class="page-head"><div class="page-copy"><h1 tabindex="-1">${title}</h1><p>${text}</p></div><div class="page-actions">${actions || ''}</div></header>`;
}
function empty(title, text, icon, actions) {
  return `<div class="empty"><span class="empty-icon" aria-hidden="true">${svg(icon || 'inventory')}</span><h3>${title}</h3><p class="muted">${text}</p>${actions ? `<div class="empty-actions">${actions}</div>` : ''}<p class="empty-help">Not sure what to do? <button class="link-button" type="button" data-action="go-help">Open Help</button></p></div>`;
}
function navButton(label, view, kind, navTab) {
  const tab = navTab ? ` data-nav-tab="${esc(navTab)}"` : '';
  return `<button class="btn ${kind || 'secondary'}" type="button" data-nav="${view}"${tab}>${label}</button>`;
}
function daysAgo(value) {
  if (!value) return Infinity;
  const raw = String(value);
  const parsed = new Date(raw.includes('T') ? raw : raw.replace(' ', 'T') + 'Z');
  return Number.isNaN(parsed.getTime()) ? Infinity : (Date.now() - parsed.getTime()) / 86400000;
}
function officeInfo() {
  const row = (icon, label, value) => `<li><span class="icon-tile sm">${svg(icon)}</span><div><span class="lbl">${label}</span><span class="val">${value}</span></div></li>`;
  return `<ul class="info-list">${row('pin', 'Where', esc(`${OFFICE.name}, ${OFFICE.place}`))}${row('clock', 'Hours', esc(OFFICE.hours))}${row('mail', 'CSA email', `<a href="mailto:${esc(OFFICE.email)}">${esc(OFFICE.email)}</a>`)}${row('phone', 'CSA phone', `<a href="tel:${esc(OFFICE.phone.replace(/[^\d+]/g, ''))}">${esc(OFFICE.phone)}</a><span class="val-note">${esc(OFFICE.phoneNote)}</span>`)}</ul>`;
}
function tabs(group, items) {
  return `<div class="tabs" role="tablist">${items.map(([key, label, count]) => {
    const on = state.tab[group] === key;
    const n = Number(count);
    const badge = Number.isFinite(n) ? `<span class="tab-count">${n}</span>` : '';
    return `<button class="tab" type="button" role="tab" data-tab-group="${group}" data-tab-value="${key}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${label}${badge}</button>`;
  }).join('')}</div>`;
}
function categoryOptions(selected, blank) {
  const current = selected || '';
  const head = `<option value="" ${current ? '' : 'selected'}>${esc(blank)}</option>`;
  const groups = CATEGORY_GROUPS.map(([name, items]) => `<optgroup label="${esc(name)}">${items.map(([key, text]) => `<option value="${esc(key)}" ${key === current ? 'selected' : ''}>${esc(text)}</option>`).join('')}</optgroup>`).join('');
  return head + groups;
}
function categorySelect() {
  return `<label class="search-box">Category<select data-list-filter="category" aria-label="Filter by category">${categoryOptions(state.category, 'All categories')}</select></label>`;
}
function inCategory(row) {
  return !state.category || row.category === state.category;
}
function listSummary(text) {
  return `<p class="list-summary">${text}</p>`;
}
function newestFirst(list) {
  return [...list].sort((a, b) => Number(b.id) - Number(a.id));
}
function searchBox(label, placeholder) {
  return `<label class="search-box">${label}<input class="search-input" value="${esc(state.query)}" placeholder="${esc(placeholder)}" aria-label="${esc(label)}"></label>`;
}
function pageOf(list, key, size) {
  size = size || PAGE_SIZE;
  const pages = Math.max(1, Math.ceil(list.length / size));
  const page = Math.min(state.page[key] || 1, pages);
  state.page[key] = page;
  const start = (page - 1) * size;
  return { rows: list.slice(start, start + size), page, pages, total: list.length, size, from: list.length ? start + 1 : 0, to: Math.min(start + size, list.length) };
}
function pager(key, info) {
  if (info.total <= (info.size || PAGE_SIZE)) return '';
  const atStart = info.page <= 1;
  const atEnd = info.page >= info.pages;
  return `<nav class="pager" aria-label="Pages"><button class="btn" type="button" data-page-key="${key}" data-dir="-1" ${atStart ? 'disabled title="You are on the first page"' : ''}>Previous</button><span>Showing ${info.from}–${info.to} of ${info.total}</span><button class="btn" type="button" data-page-key="${key}" data-dir="1" ${atEnd ? 'disabled title="You are on the last page"' : ''}>Next</button></nav>`;
}
function hit(parts) {
  if (!state.query) return true;
  return parts.join(' ').toLowerCase().includes(state.query.toLowerCase());
}

function aiStatus() {
  const action = arguments[0];
  const info = state.data.matching_status || {};
  const on = Boolean(info.ready);
  const localDefault = 'Matching runs on this computer with DINOv2 and CLIP. Photos never leave the server.';
  const line = on
    ? (info.reason ? esc(info.reason) : localDefault)
    : `No model is loaded. Matches use color, brand, place, date, and owner-only marks. ${esc(info.reason || '')}`.trim();
  return `<section class="ai-card ${on ? 'on' : 'off'}" aria-label="AI matching status"><span class="icon-tile sm" aria-hidden="true">${svg('spark')}</span><div><p class="kicker">AI-assisted matching</p><h2 class="h3-size">AI is ${on ? 'on' : 'off'}</h2><p class="meta">${line}</p></div>${action || ''}</section>`;
}
function personLine() {
  const user = state.user || {};
  const name = String(user.name || 'there').trim();
  const number = String(user.student_number || '').trim();
  const role = admin() ? 'CSA staff' : user.role === 'professor' ? 'Professor' : user.role === 'guest' ? 'Guest' : 'Student';
  return { name, meta: number || role };
}
function dayGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return ['Good morning', 'sun'];
  if (hour < 18) return ['Good afternoon', 'sun'];
  return ['Good evening', 'moon'];
}
function greetCard(actions) {
  const [hello] = dayGreeting();
  const { name } = personLine();
  const date = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  return `<section class="greet desk-head" aria-label="${esc(hello)}"><span class="greet-avatar" aria-hidden="true">${esc(initials())}</span><div class="greet-copy"><p class="greet-welcome">Welcome, ${esc(name)}</p><h1 class="greet-hello">${hello}</h1></div><div class="greet-side"><p class="greet-date">${esc(date)}</p>${actions || ''}</div></section>`;
}
function kpi(view, icon, label, count, hint, navTab) {
  const tab = navTab ? ` data-nav-tab="${esc(navTab)}"` : '';
  return `<button class="stat stat-link${count ? '' : ' is-zero'}" type="button" data-nav="${view}"${tab}><span class="stat-icon" aria-hidden="true">${svg(icon)}</span><div><span>${label}</span><strong>${count}</strong><small>${hint}</small></div><span class="stat-arrow" aria-hidden="true">${svg('arrow')}</span></button>`;
}
function staffSearchHits() {
  const rows = [];
  const push = (title, meta, view) => rows.push({ title, meta, view });
  arr('reports').forEach(report => {
    if (hit([report.description, report.owner_name, report.place, report.category, catName(report.category)])) push(report.description, `${report.owner_name || 'Owner'} · Lost report · ${report.place || ''}`, 'lost');
  });
  arr('items').forEach(item => {
    if (hit([item.description, item.place, item.color, item.brand, item.finder_name, catName(item.category)])) push(item.description, `${item.place || 'Office'} · Found item`, 'items');
  });
  arr('matches').forEach(match => {
    if (hit([match.item_description, match.report_description, match.owner_name, catName(match.category)])) push(match.item_description || 'Match', `${match.owner_name || 'Owner'} · Match`, 'matches');
  });
  arr('claims').forEach(claim => {
    if (hit([claim.item_description, claim.report_description, claim.claimant_name, claim.claimant_student_number])) push(claimTitle(claim), `${claim.claimant_name || 'Owner'} · Claim`, 'claims');
  });
  return rows.slice(0, 12);
}
function searchOpen(label, view) {
  return `<button class="btn secondary sm" type="button" data-action="search-open" data-id="${esc(view)}">${esc(label)}</button>`;
}
function cardSlide(grid, extra) {
  return `<div class="card-slide"><div class="card-rail">${grid}</div>${extra || ''}</div>`;
}
function deskColumn(id, title, rows, view, count, opts) {
  opts = opts || {};
  const n = Number(count) || 0;
  const mark = n ? `<span class="tab-count">${n}</span>` : '';
  const icon = opts.icon ? `<span class="icon-tile sm" aria-hidden="true">${svg(opts.icon)}</span>` : '';
  const inner = rows.length ? `<div class="list">${rows.join('')}</div>` : `<p class="muted desk-empty">${opts.empty || 'None right now.'}</p>`;
  const body = `<div class="desk-scroll">${inner}</div>`;
  const all = opts.viewAll != null ? opts.viewAll : navButton('View all', view, 'secondary sm');
  return `<section class="card desk-col" aria-labelledby="${id}"><div class="card-head"><h2 id="${id}">${icon}${title}${mark}</h2>${all}</div>${body}</section>`;
}
function deskLead(desk) {
  return desk.total ? '' : '<p class="greet-lead">Nothing is waiting.</p>';
}
function pageFor(list, id) {
  return Math.floor(Math.max(0, list.findIndex(row => String(row.id) === String(id))) / PAGE_SIZE) + 1;
}
function openLostRow(id) {
  state.view = 'lost';
  state.tab.lost = 'need';
  state.query = '';
  state.category = '';
  state.quick = null;
  state.filter = '';
  state.page = {};
  state.page.lost = pageFor(sortLost(arr('reports').filter(report => lostWork(report) === 'need')), id);
  state.focusId = `lost-${id}`;
  closeMenu(false);
  render();
}
function openFoundRow(id) {
  state.view = 'items';
  state.tab.items = 'waiting';
  state.query = '';
  state.category = '';
  state.quick = null;
  state.filter = '';
  state.page = {};
  state.page.items = pageFor(newestFirst(arr('found_reports').filter(report => report.status === 'awaiting_turn_in')), id);
  state.focusId = `found-${id}`;
  closeMenu(false);
  render();
}
function openMatchRow(id) {
  state.view = 'matches';
  state.tab.matches = 'review';
  state.query = '';
  state.category = '';
  state.quick = null;
  state.filter = '';
  state.page = {};
  const pool = arr('matches').filter(match => match.status === 'suggested').sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0) || Number(b.id) - Number(a.id));
  state.page.matches = pageFor(pool, id);
  state.focusId = `match-${id}`;
  closeMenu(false);
  render();
}
function renderToday() {
  if (state.query.trim()) {
    const hits = staffSearchHits();
    const labels = { lost: 'View lost reports', items: 'View found items', matches: 'View matches', claims: 'View claims' };
    const list = hits.map(row => `<div class="list-row"><div class="grow"><strong>${esc(row.title)}</strong><p class="meta">${esc(row.meta)}</p></div>${searchOpen(labels[row.view], row.view)}</div>`).join('');
    return `<div class="page-stack">${pageHead('Search', `Results for “${state.query.trim()}”`)}<section class="card">${list || empty('No results', 'Try the item name, owner, or place.', 'search')}</section></div>`;
  }
  const desk = deskCounts();
  const waiting = waitingClaims();
  const suggestions = arr('matches').filter(match => match.status === 'suggested').sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
  const needed = sortLost(arr('reports').filter(report => lostWork(report) === 'need'));
  const arriving = arr('found_reports').filter(report => report.status === 'awaiting_turn_in' && !report.hidden);
  const returned = doneThisWeek();
  const rowHtml = (icon, title, meta, status, action, id, tag) => `<button class="inbox-row" type="button" data-action="${esc(action)}" data-id="${esc(id)}"><span class="icon-tile sm" aria-hidden="true">${icon}</span><span class="grow"><strong>${esc(title)}</strong><span class="meta">${esc(meta)}</span></span>${tag ? `<span class="inbox-row-tag">${esc(tag)}</span>` : ''}${status || ''}<span class="inbox-row-arrow" aria-hidden="true">${svg('arrow')}</span></button>`;
  const lostMeta = report => report.flagged ? `${report.owner_name || 'Guest'} · Needs check` : `${report.owner_name || 'Owner'} · ${report.place || 'Campus'}`;
  const claimRows = waiting.map(claim => rowHtml(catIcon(claim.item_category), claimTitle(claim), claim.claimant_name || 'Owner', badge(claim), 'open-claim', claim.id));
  const matchRows = suggestions.map(match => rowHtml(catIcon(match.category), match.item_description || 'Item', `${match.owner_name || 'Owner'} · ${match.report_description || ''}`, `<span class="score-pill ${match.level === 'strong' ? 'strong' : 'possible'}">${matchLabel(match)}</span>`, 'open-match', match.id));
  const lostRows = needed.map(report => rowHtml(catIcon(report.category), report.description, lostMeta(report), badge(report), 'open-lost', report.id));
  const foundRows = arriving.map(report => rowHtml(catIcon(report.category), report.description, report.place || 'Campus', badge(report), 'open-found', report.id));
  const returnedRows = returned.map(claim => rowHtml(catIcon(claim.item_category), claimTitle(claim), `${claim.claimant_name || 'Owner'} · ${dateText(claim.released_at)}`, '', 'open-claim', claim.id));
  const priorityRows = [
    ...waiting.map(claim => rowHtml(catIcon(claim.item_category), claimTitle(claim), claim.claimant_name || 'Owner', badge(claim), 'open-claim', claim.id, 'Claim')),
    ...suggestions.map(match => rowHtml(catIcon(match.category), match.item_description || 'Item', match.owner_name || 'Owner', `<span class="score-pill ${match.level === 'strong' ? 'strong' : 'possible'}">${matchLabel(match)}</span>`, 'open-match', match.id, 'Match')),
    ...needed.filter(r => r.flagged).map(report => rowHtml(catIcon(report.category), report.description, lostMeta(report), badge(report), 'open-lost', report.id, 'Guest check')),
    ...arriving.map(report => rowHtml(catIcon(report.category), report.description, report.place || 'Campus', badge(report), 'open-found', report.id, 'Arriving')),
    ...needed.filter(r => !r.flagged).map(report => rowHtml(catIcon(report.category), report.description, lostMeta(report), badge(report), 'open-lost', report.id, 'Lost')),
  ];
  const validTabs = ['all', 'claims', 'matches', 'lost', 'arriving', 'done'];
  const activeTab = validTabs.includes(state.tab.desk) ? state.tab.desk : 'all';
  const viewMap = { all: '', claims: 'claims', matches: 'matches', lost: 'lost', arriving: 'items', done: '' };
  const rowMap = { all: priorityRows, claims: claimRows, matches: matchRows, lost: lostRows, arriving: foundRows, done: returnedRows };
  const emptyMap = {
    all: ['Nothing is waiting', 'All claims, matches, and reports are caught up.'],
    claims: ['No pending claims', 'Claims appear here after owners answer ownership questions.'],
    matches: ['No matches to review', 'New matches appear automatically when items and reports overlap.'],
    lost: ['No open lost reports', 'New lost reports awaiting action will show here.'],
    arriving: ['Nothing awaiting arrival', 'Found reports waiting to reach the CSA office show here.'],
    done: ['No returns this week', 'Items handed back appear here for 7 days.'],
  };
  const activeRows = rowMap[activeTab] || [];
  const [emptyTitle, emptyText] = emptyMap[activeTab];
  const headAction = activeTab === 'done'
    ? (returned.length ? '<button class="btn secondary sm" type="button" data-quick="done">View all</button>' : '')
    : activeTab === 'matches'
      ? button('Find matches', 'run-matching', '', 'secondary sm')
      : viewMap[activeTab]
        ? navButton('View all', viewMap[activeTab], 'secondary sm')
        : '';
  const tiles = `<div class="stats area-stats" aria-label="Desk summary">${kpi('lost', 'documents', 'Lost reports', desk.need, desk.need ? 'Action needed' : 'None waiting')}${kpi('items', 'inventory', 'Awaiting arrival', desk.arriving, desk.arriving ? 'On the way' : 'All received')}${kpi('matches', 'match', 'Matches', suggestions.length, suggestions.length ? 'To review' : 'None pending')}${kpi('claims', 'shield', 'Claims', waiting.length, waiting.length ? 'To review' : 'None pending')}</div>`;
  const inboxTabs = tabs('desk', [
    ['all', 'Needs attention', priorityRows.length],
    ['claims', 'Claims', waiting.length],
    ['matches', 'Matches', suggestions.length],
    ['lost', 'Lost', desk.need],
    ['arriving', 'Arriving', desk.arriving],
    ['done', 'Returned', returned.length],
  ]);
  const inboxBody = activeRows.length
    ? `<div class="desk-inbox-body">${activeRows.slice(0, 12).join('')}</div>`
    : `<div class="desk-inbox-empty"><strong>${esc(emptyTitle)}</strong><span>${esc(emptyText)}</span></div>`;
  const inbox = `<section class="desk-inbox area-inbox" aria-labelledby="desk-inbox-h"><div class="desk-inbox-head"><h2 id="desk-inbox-h">Desk queue${priorityRows.length ? `<span class="tab-count">${priorityRows.length}</span>` : ''}</h2>${headAction}</div><div class="desk-inbox-tabs">${inboxTabs}</div>${inboxBody}</section>`;
function campusHotspots() {
  const lost = arr('lost_reports');
  const found = arr('found_reports');
  const items = arr('items');
  const claims = arr('claims');
  const counts = new Map();
  [...lost, ...found, ...items].forEach(entry => {
    const place = String(entry.place || '').trim();
    if (!place) return;
    counts.set(place, (counts.get(place) || 0) + 1);
  });
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5);
  const max = top[0]?.[1] || 1;
  const totalLogged = lost.length + items.length;
  const returnedCount = claims.filter(claim => claim.status === 'released').length;
  const rate = totalLogged ? Math.round((returnedCount / totalLogged) * 100) : 0;
  const bars = top.length
    ? `<div class="hotspot-bars">${top.map(([place, count]) => `<div class="hotspot-row"><div class="hotspot-label"><span>${esc(place)}</span><strong>${count}</strong></div><div class="hotspot-track"><div class="hotspot-fill" style="width:${Math.max(10, Math.round((count / max) * 100))}%"></div></div></div>`).join('')}</div>`
    : '<p class="home-recent-empty">No campus locations logged yet. Top buildings and recovery rate will appear here as reports arrive.</p>';
  return `<section class="card hotspot-card" aria-labelledby="hotspot-h"><div class="card-head"><h2 id="hotspot-h">Campus hotspots</h2><span class="meta">${returnedCount} returned · ${rate}% recovery rate</span></div>${bars}</section>`;
}
  const actions = `<div class="banner-actions">${button('Receive item', 'receive', '', 'primary')}${button('Report for a guest', 'guest-lost', '', 'soft')}</div>`;
  return `<div class="page-stack desk-home area-home">${greetCard(actions)}${tiles}${inbox}${campusHotspots()}${aiStatus()}</div>`;
}
function actionText(action) {
  const text = String(action || '').replaceAll('_', ' ').toLowerCase();
  const words = { 'step1 passed': 'Online check approved', 'step2 passed': 'Office check approved', 'in person consent recorded': 'Office check started', 'item released': 'Item handed over', 'matching run': 'Matches found', 'ai unavailable': 'AI was off, typed details used', 'user blocked': 'Account blocked', 'user unblocked': 'Account unblocked', 'report hidden': 'Report hidden', 'report restored': 'Report shown again', 'report checked': 'Guest report checked', 'roster added': 'Allowed email added', 'roster on': 'Allowed email switched on', 'roster off': 'Allowed email switched off', 'roster removed': 'Allowed email removed', 'roster imported': 'Allowed emails imported', 'password changed': 'Password changed', 'password set': 'Password set at the desk', 'profile updated': 'Profile updated' };
  return words[text] || text.replace(/^./, ch => ch.toUpperCase()).replace(/^Ai /, 'AI ');
}
function claimableInvites() {
  const claims = arr('claims');
  return arr('matches').filter(match => match.status === 'confirmed' && !claims.some(claim => String(claim.item_id) === String(match.item_id) && String(claim.report_id) === String(match.report_id) && claim.status !== 'rejected'));
}
function renderHome() {
  const source = journey();
  const itemTitle = journeyTitle(source);
  const guest = state.user.role === 'guest';
  const reports = arr('reports');
  const claims = arr('claims');
  const invites = arr('matches').filter(match => match.status === 'confirmed').length;
  const openCount = reports.filter(report => report.status === 'open').length;
  const waitingInvites = claimableInvites().length;
  const inProgress = claims.filter(claim => !['released', 'rejected'].includes(claim.status)).length;
  const returnedCount = claims.filter(claim => claim.status === 'released').length;

  const homeActions = `<div class="banner-actions">${button('Report a lost item', 'lost', '', 'primary')}${guest ? '' : button('Report a found item', 'found', '', 'soft')}</div>`;

  const step = memberNextStepData();
  const statusCard = (step.title || itemTitle)
    ? `<section class="area-status-split" aria-labelledby="next-action-title">
        <div class="area-status-main">
          ${step.title ? `<p class="kicker">Your next step</p><h2 id="next-action-title">${esc(step.title)}</h2><p class="area-status-copy">${esc(step.text)}</p>` : ''}
          ${itemTitle ? `<div class="area-status-tracker">${tracker(source, false, true)}</div>` : ''}
        </div>
        <div class="area-status-panel wix-status-card">
          <div class="wix-status-photo"><img src="/assets/campus.jpg?v=244" alt="Lyceum of the Philippines University Cavite campus" loading="lazy"></div>
          <div class="wix-status-body">
            <p class="kicker area-panel-eyebrow">${itemTitle ? 'Active item' : 'LPU Cavite CSA'}</p>
            <strong class="area-panel-title">${esc(itemTitle || (guest ? 'Bring found items to CSA' : 'Ready when you are'))}</strong>
            <p class="area-panel-note">${guest && !itemTitle ? 'Guests bring found items directly to the CSA office at Gate 1.' : 'Follow your item across four clear steps with CSA verification.'}</p>
            <div class="area-panel-actions">${step.action || button('Report a lost item', 'lost', '', 'primary sm')}</div>
          </div>
        </div>
      </section>`
    : '';

  const tiles = `<div class="stats area-stats" aria-label="Your summary">${kpi('reports', 'documents', 'Open reports', openCount, openCount ? 'Looking for match' : 'None open')}${kpi('claims', 'match', 'Invitations', waitingInvites, waitingInvites ? 'Ready to answer' : 'None yet', 'myclaims:invites')}${kpi('claims', 'shield', 'Claims', inProgress, inProgress ? 'In verification' : 'None active', 'myclaims:progress')}${kpi('claims', 'check', 'Returned', returnedCount, returnedCount ? 'Handed back' : 'None yet', 'myclaims:returned')}</div>`;

  const reportRows = reports.slice(0, 4).map(report => `<button class="inbox-row" type="button" data-action="open-lost" data-id="${esc(report.id)}"><span class="icon-tile sm" aria-hidden="true">${catIcon(report.category)}</span><span class="grow"><strong>${esc(report.description)}</strong><span class="meta">${esc(report.place)} · ${esc(dateText(report.date_lost))}</span></span>${badge(report)}</button>`).join('');
  const reportsCard = `<section class="area-list-section" aria-labelledby="rep-h"><div class="card-head"><h2 id="rep-h">Recent reports</h2>${reports.length ? `<button class="btn soft sm" type="button" data-nav="reports">View all</button>` : ''}</div>${reports.length ? `<div class="list">${reportRows}</div>` : '<p class="home-recent-empty">No reports yet. Use Report a lost item above to start.</p>'}</section>`;

  const claimRows = claims.slice(0, 4).map(claim => `<button class="inbox-row" type="button" data-action="open-claim" data-id="${esc(claim.id)}"><span class="icon-tile sm" aria-hidden="true">${catIcon(claim.item_category)}</span><span class="grow"><strong>${esc(claimTitle(claim))}</strong><span class="meta">${esc(catName(claim.item_category))}</span></span>${badge(claim)}</button>`).join('');
  const claimsTab = inProgress ? 'myclaims:progress' : waitingInvites ? 'myclaims:invites' : 'myclaims:returned';
  const claimsCard = `<section class="area-list-section" aria-labelledby="clm-h"><div class="card-head"><h2 id="clm-h">Recent claims</h2>${claims.length || invites ? navButton('View all', 'claims', 'soft sm', claimsTab) : ''}</div>${claimRows ? `<div class="list">${claimRows}</div>` : invites ? `<div class="list-row"><span class="icon-tile sm" aria-hidden="true">${svg('shield')}</span><div class="grow"><strong>You have a match invitation</strong><p class="meta">Answer a few questions to claim your item.</p></div>${navButton('Claim item', 'claims', 'primary sm', 'myclaims:invites')}</div>` : '<p class="home-recent-empty">When CSA confirms a match, your claim shows up here.</p>'}</section>`;

  return `<div class="page-stack area-home">${greetCard(homeActions)}<div data-report-drafts>${reportDraftNotice()}</div>${tiles}${statusCard}<div class="grid-2 area-recent-grid">${reportsCard}${claimsCard}</div><p class="home-foot">Need office hours or status details? Open <button class="link-button" type="button" data-action="go-help">Help</button>.</p></div>`;
}
function reportDraftNotice() {
  const drafts = window.LyFindReports?.list(state.user,state.config.demo_mode?'test':'live') || [];
  if (!drafts.length) return '';
  return `<section class="card draft-notice" aria-label="Unfinished reports"><h2>Pick up where you left off</h2>${drafts.map(draft=>`<div class="list-row"><span class="grow">Unfinished ${draft.kind === 'found'?'found':'lost'} report</span>${button('Resume draft','report-draft',draft.kind,'secondary sm')}</div>`).join('')}<p class="meta">Saved on this browser for your account.</p></section>`;
}
function memberNextStepData() {
  const claims=arr('claims');
  const visit=claims.find(row=>['step2_pending','approved'].includes(row.status));
  const invitation=claimableInvites().find(row=>row.can_claim!==false);
  const handoff=arr('found_reports').find(row=>row.status==='awaiting_turn_in' && row.where_now==='with_me');
  const active=claims.find(row=>!['rejected','released'].includes(row.status));
  const report=arr('reports').find(row=>row.status==='open');
  let title='',text='',action='';
  if(visit){title='Bring your ID to CSA';text=visit.status==='approved'?'Your claim is approved. Visit the office for physical handover.':'Your online check passed. Visit CSA with a valid ID for the in-person check.';action=button('View claim','open-claim',visit.id,'primary sm');}
  else if(invitation){title='Answer the ownership questions';text='CSA confirmed a possible match. Share details only the owner would know.';action=button('Answer questions','claim',invitation.id,'primary sm');}
  else if(handoff){title='Bring the found item to CSA';text=`Your report is saved. Surrender the item${handoff.turn_in_deadline?` by ${dateText(handoff.turn_in_deadline)}`:''} so CSA can match it.`;action=button('View found report','open-found',handoff.id,'secondary sm');}
  else if(active){title='Waiting for CSA review';text=active.status==='verified'?'Both checks passed. CSA will approve your pickup shortly.':'Your answers were sent. CSA will notify you once reviewed.';action=button('View claim','open-claim',active.id,'secondary sm');}
  else if(report){title=report.flagged?'Waiting for CSA check':'Looking for a match';text=report.flagged?'CSA reviews guest reports first. Your report is saved.':'CSA will notify you as soon as a matching item is confirmed.';action=button('View report','open-lost',report.id,'secondary sm');}
  else {const rejected=claims.find(row=>row.status==='rejected');const found=arr('found_reports').find(row=>row.status==='awaiting_turn_in');if(rejected){title='Read CSA’s decision';text='Check the note from CSA before trying again.';action=button('Read decision','open-claim',rejected.id,'secondary sm');}else if(found){title='Waiting for CSA collection';text=found.where_now==='security'?'CSA will collect the item from campus security.':'CSA has your found report.';action=button('View found report','open-found',found.id,'secondary sm');}}
  return { title, text, action };
}
function memberNextStep() {
  const { title, text, action } = memberNextStepData();
  return title?`<section class="card next-action" aria-labelledby="next-action-title"><div><p class="kicker">Your next step</p><h2 id="next-action-title">${esc(title)}</h2><p>${esc(text)}</p></div>${action}</section>`:'';
}
function reportCard(report) {
  return `<article class="report-card" data-sheet="lost" data-id="${esc(report.id)}"><div class="status-corner">${badge(report)}</div><div class="report-top"><span class="item-icon" aria-hidden="true">${catIcon(report.category)}</span><div class="report-copy"><h3>${esc(report.description)}</h3><p class="meta">${esc(report.place)}</p>${dateLine(report.date_lost, 'Date lost')}${timeLine(report.time_lost)}${tracker(sourceForReport(report), true)}</div></div></article>`;
}
function renderReports() {
  const guest = state.user.role === 'guest';
  const lostAll = arr('reports');
  const foundAll = arr('found_reports');
  const total = lostAll.length + foundAll.length;
  const lost = state.tab.reports !== 'found';
  const source = lost ? lostAll : foundAll;
  const list = newestFirst(source.filter(row =>
    inCategory(row) && hit([row.description, row.place, row.status_label, row.category, catName(row.category)])));
  const open = list.filter(row => lost ? row.status !== 'closed' : row.status === 'awaiting_turn_in');
  const done = list.filter(row => lost ? row.status === 'closed' : row.status !== 'awaiting_turn_in');
  const showKindTabs = total > 0;
  const showStatusTabs = source.length >= 3;
  if (!showStatusTabs) state.tab.mine = 'open';
  const view = state.query.trim() ? list : (showStatusTabs && state.tab.mine === 'done' ? done : showStatusTabs ? open : list);
  const info = pageOf(view, 'mine');
  const cards = info.rows.map(row => lost ? reportCard(row) : foundCard(row)).join('');
  const looking = !showStatusTabs || state.tab.mine !== 'done';
  const none = state.query.trim()
    ? ['No reports match', 'Try a different word, or clear the search.']
    : !source.length
    ? (lost
      ? ['No reports yet', 'Lost or found something? Use the button above.']
      : ['No found reports yet', 'Found something? Report it, then bring it to the CSA office.'])
    : lost
      ? [looking ? 'No open reports' : 'No closed reports', looking ? 'Nothing matches this filter.' : 'Closed reports stay here so you can look back.']
      : [looking ? 'Nothing on the way to CSA' : 'Nothing received yet', looking ? 'Nothing matches this filter.' : 'Items CSA already received are listed here.'];
  const actions = total === 0
    ? button('Report lost', 'lost', '', 'primary') + button('Report found', 'found', '', 'secondary')
    : (lost ? button('Report lost', 'lost', '', 'primary') : button('Report found', 'found', '', 'primary'));
  const blurb = total === 0
    ? 'Report a lost or found item. CSA looks for a match and keeps you on the same four steps.'
    : (lost ? 'Items you reported as lost. Follow each one from Reported to Released.' : 'Items you found. Bring each one to the CSA office if you still have it.');
  return pageHead('My reports', blurb, actions)
    + (showKindTabs ? tabs('reports', [['lost', 'Lost', lostAll.length], ['found', 'Found', foundAll.length]]) : '')
    + (showStatusTabs ? tabs('mine', [['open', 'Open', open.length], ['done', 'Done', done.length]]) : '')
    + (source.length ? `<div class="toolbar">${searchBox('Search', 'Search your reports')}${categorySelect()}</div>` : '')
    + (view.length ? listSummary(`${info.total} ${info.total === 1 ? 'report' : 'reports'} in this view.`) : '')
    + srHeading(lost ? 'Your lost reports' : 'Your found reports')
    + (cards ? `<div class="cards">${cards}</div>${pager('mine', info)}` : empty(none[0], none[1], lost ? 'documents' : 'inventory'));
}
const WHERE_TEXT = { with_me: ['Finder has it', 'You have it'], security: ['With campus security', 'With campus security'], left: ['Left where it was found', 'Left where you found it'] };
function timeLine(value) {
  return value && value !== 'Not sure' ? `<p class="meta">About ${esc(String(value).toLowerCase())}</p>` : '';
}
function foundCard(report) {
  const staff = admin();
  const desk = staff ? foundDesk(report) : null;
  const now = report.where_now || 'with_me';
  const noteText = { with_me: 'Bring this item to the CSA office. It cannot be claimed until then.', security: 'CSA will collect this from campus security. It cannot be claimed until it reaches the office.', left: 'CSA may check the place you named. It cannot be claimed until it reaches the office.' }[now];
  const note = !staff && report.status === 'awaiting_turn_in' ? `<p class="note" role="note">${noteText}</p>` : '';
  const who = staff ? whoLine('Reported by', report.finder_name || 'a finder', report.finder_role, '', '', '') : '';
  const next = staff && desk.next ? `<p class="next-step"><b>Next:</b> ${esc(desk.next)}</p>` : '';
  const hidden = report.hidden ? '<span class="tag">Hidden</span>' : '';
  const tools = staff ? `${desk.primary}${desk.hide}` : '';
  const looks = [catName(report.category), report.color, report.brand && report.brand !== 'Unbranded' ? report.brand : ''].filter(Boolean).map(esc).join(' · ');
  const photo = report.photo_id ? `<img class="thumb" alt="Photo from the finder, visible to staff and the finder only" src="/api/files/${encodeURIComponent(report.photo_id)}">` : `<span class="item-icon" aria-hidden="true">${catIcon(report.category)}</span>`;
  const when = `${dateLine(report.date_found, 'Date found')}${timeLine(report.time_found)}${report.status === 'awaiting_turn_in' && now === 'with_me' ? dateLine(report.turn_in_deadline, 'Bring in by') : ''}${report.status !== 'awaiting_turn_in' ? dateLine(report.received_at || report.date_found, 'Received') : ''}`;
  const facts = `<div class="card-facts">${when}${hidden ? `<div class="pills">${hidden}</div>` : ''}</div>`;
  return `<article class="record" id="found-${esc(report.id)}" data-sheet="found" data-id="${esc(report.id)}"><div class="status-corner">${badge(report)}</div><div class="report-top">${photo}<div class="report-copy"><h3>${esc(report.description)}</h3><p class="meta">${esc(report.place)}</p>${looks ? `<p class="meta">${looks}</p>` : ''}${who}${report.status === 'awaiting_turn_in' ? `<p class="meta">${WHERE_TEXT[now][staff ? 0 : 1]}</p>` : ''}${facts}</div></div>${note}${next}<div class="row-actions">${tools}</div></article>`;
}
function activeClaimFor(key, id) {
  return arr('claims').find(claim => String(claim[key]) === String(id) && ACTIVE_CLAIM.includes(claim.status));
}
function itemCard(item) {
  const claim = activeClaimFor('item_id', item.id);
  const primary = claim ? button('Review claim', 'open-claim', claim.id, 'primary') : button('View item', 'view-item', item.id, 'primary');
  const more = claim ? moreMenu([['View item', 'view-item', item.id]]) : '';
  const photo = item.photo_id ? `<img class="thumb" alt="Photo of the item, visible to staff only" src="/api/files/${encodeURIComponent(item.photo_id)}">` : `<span class="item-icon" aria-hidden="true">${catIcon(item.category)}</span>`;
  const details = [catName(item.category), item.color, item.place].filter(Boolean).map(esc).join(' · ');
  const facts = `<div class="card-facts">${dateLine(item.date_found, 'Date found')}${item.received_at ? dateLine(item.received_at, 'Received') : ''}</div>`;
  return `<article class="record" data-sheet="item" data-id="${esc(item.id)}"><div class="status-corner">${badge(item)}</div><div class="report-top">${photo}<div class="report-copy"><h3>${esc(item.description)}</h3><p class="meta">${details}</p>${facts}</div></div><div class="row-actions">${primary}${more}</div></article>`;
}
function renderItems() {
  const office = state.tab.items !== 'waiting';
  const waiting = arr('found_reports').filter(report => report.status === 'awaiting_turn_in');
  let items = office ? arr('items') : waiting;
  items = items.filter(item => inCategory(item) && hit([item.description, item.category, item.place, item.color, item.brand, item.finder_name, item.status_label]));
  if (office && state.filter) items = items.filter(item => item.status === state.filter);
  items = office && state.filter === 'available'
    ? [...items].sort((a, b) => (b.active_claims ? 1 : 0) - (a.active_claims ? 1 : 0) || Number(b.id) - Number(a.id))
    : newestFirst(items);
  const info = pageOf(items, 'items');
  const body = office
    ? (info.rows.length ? cardSlide(`<div class="cards desk-list">${info.rows.map(itemCard).join('')}</div>`) : empty('No items in this view', 'Try another filter, or receive an item.', 'inventory', button('Receive item', 'receive', '', 'primary')))
    : (info.rows.length ? cardSlide(`<div class="cards desk-list">${info.rows.map(foundCard).join('')}</div>`) : empty('Nothing is awaiting arrival', 'When someone reports a found item, it shows here until it reaches the office.', 'inventory'));
  const filter = office ? `<label class="search-box">Status<select id="item-filter" aria-label="Filter by status"><option value="">All statuses</option>${[['available', 'In the office'], ['under_verification', 'Being checked'], ['released', 'Handed back'], ['unclaimed', 'Not claimed']].map(([value, label]) => `<option value="${value}" ${state.filter === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>` : '';
  const quick = state.quick === 'office' && office ? QUICK.office : null;
  const filterLabel = office && state.filter ? ({ available: 'In the office', under_verification: 'Being checked', released: 'Handed back', unclaimed: 'Not claimed' }[state.filter] || state.filter) : '';
  return pageHead(quick ? quick.title : 'Found items', quick ? quick.text : office ? 'Items already at the CSA office. Use the status filter to see items being checked or already handed back.' : 'Found reports that have not reached the office yet. Nobody can claim these until you receive the item.', button('Receive item', 'receive', '', 'primary'))
    + tabs('items', [['office', 'In the office', arr('items').length], ['waiting', 'Awaiting arrival', waiting.length]])
    + (filterLabel ? filterChip(filterLabel, info.total, 'item') : '')
    + `<div class="toolbar">${searchBox('Search', 'Search by name or place')}${categorySelect()}${filter}</div>`
    + srHeading(office ? 'Items in the office' : 'Items on the way') + body + pager('items', info);
}
function bestMatch(matches, status) {
  return matches.filter(match => match.status === status).sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0))[0];
}
function reportTags(report) {
  const tags = [report.owner_role === 'guest' ? '<span class="tag">Guest</span>' : '', report.flagged && !report.hidden ? '<span class="tag warn">Needs a check</span>' : '', report.hidden ? '<span class="tag">Hidden</span>' : ''].filter(Boolean);
  return tags.length ? `<div class="pills">${tags.join('')}</div>` : '';
}
function whoLine(prefix, name, role, email, phone, number) {
  const extra = [roleLabel(role), number, email, phone].filter(Boolean);
  return `<p class="meta">${esc(prefix)} <b>${esc(name || 'Unknown')}</b>${extra.length ? ` · ${esc(extra.join(' · '))}` : ''}</p>`;
}
function lostDesk(report) {
  const claim = arr('claims').find(item => String(item.report_id) === String(report.id) && item.status !== 'rejected');
  const related = matchesFor('report_id', report.id);
  const suggested = bestMatch(related, 'suggested');
  let primary = '';
  let wait = '';
  let next = 'No match yet. New items are compared automatically.';
  if (report.hidden) { primary = button('Show again', 'unhide-report', report.id, 'primary'); next = 'Hidden. The owner and matching do not see it. The record is kept.'; }
  else if (report.flagged) { primary = button('Check report', 'check-report', report.id, 'primary'); next = 'A guest sent this. Check that it looks real. Matching waits until you do. Hide it if it looks like spam.'; }
  else if (report.status === 'closed') next = 'Done. The item was handed back.';
  else if (claim && claim.status !== 'released') { primary = button('Review claim', 'open-claim', claim.id, 'primary'); next = nextForClaim(claim); }
  else if (suggested) { primary = button('Review match', 'open-match', suggested.id, 'primary'); next = 'A match is waiting. Approve it to invite the owner, or reject it.'; }
  else if (related.some(match => match.status === 'confirmed')) { wait = '<span class="waiting-tag">Waiting for the owner</span>'; next = 'The owner was invited. Their answers will show in Claims.'; }
  const hide = report.hidden ? '' : button('Hide report', 'hide-report', report.id, 'secondary');
  return { primary, hide, wait, next, related, claim };
}
function foundDesk(report) {
  const now = report.where_now || 'with_me';
  const arriving = { with_me: 'When the item reaches the office, press Receive item.', security: 'Collect it from campus security, then press Receive item.', left: 'Check the place the finder named. When you have the item, press Receive item.' };
  let primary = '';
  let next = 'Received at the office. It can be matched with a lost report.';
  if (report.hidden) { primary = button('Show again', 'unhide-found', report.id, 'primary'); next = 'Hidden. The finder and the office list do not see it. The record is kept.'; }
  else if (report.status === 'awaiting_turn_in') { primary = button('Receive item', 'receive-found', report.id, 'primary'); next = arriving[now] || arriving.with_me; }
  const hide = report.hidden ? '' : button('Hide report', 'hide-found', report.id, 'secondary');
  return { primary, hide, next, now };
}
function itemDesk(item) {
  const claim = activeClaimFor('item_id', item.id);
  const related = matchesFor('item_id', item.id);
  const suggested = bestMatch(related, 'suggested');
  const primary = claim ? button('Review claim', 'open-claim', claim.id, 'primary') : suggested ? button('Review match', 'open-match', suggested.id, 'primary') : '';
  const next = claim ? nextForClaim(claim) : suggested ? 'A match is waiting. Approve it to invite the owner, or reject it.' : item.status === 'released' ? 'Handed back.' : item.status === 'unclaimed' ? 'The keep time ended. It was marked Not claimed.' : item.status === 'under_verification' ? 'Someone is checking this item.' : 'In the office. It can be matched with a lost report.';
  return { primary, next, related, claim };
}
function matchSummary(matches, side) {
  const live = matches.filter(match => match.status !== 'dismissed');
  if (!live.length) return '';
  const lines = live.map(match => {
    const state = match.status === 'confirmed' ? 'Owner invited' : 'Needs a decision';
    const title = side === 'item' ? (match.report_description || 'Lost report') : (match.item_description || 'Item in the office');
    return `<li><span>${esc(title)}</span><span>${esc(matchLabel(match))} · ${state}</span></li>`;
  }).join('');
  return `<div class="detail-related"><span class="kicker">Matches</span><ul>${lines}</ul></div>`;
}
function lostCard(report) {
  const desk = lostDesk(report);
  const facts = `<div class="card-facts">${dateLine(report.date_lost, 'Date lost')}${timeLine(report.time_lost)}${reportTags(report)}</div>`;
  const photo = report.photo_id ? `<img class="thumb" alt="Photo from the owner's report, visible to staff only" src="/api/files/${encodeURIComponent(report.photo_id)}">` : `<span class="item-icon" aria-hidden="true">${catIcon(report.category)}</span>`;
  const looks = [catName(report.category), report.color, report.brand && report.brand !== 'Unbranded' ? report.brand : ''].filter(Boolean).map(esc).join(' · ');
  const showNext = report.flagged || report.hidden;
  return `<article class="record" id="lost-${esc(report.id)}" data-sheet="lost" data-id="${esc(report.id)}"><div class="status-corner">${badge(report)}</div><div class="report-top">${photo}<div class="report-copy"><h3>${esc(report.description)}</h3><p class="meta">${esc(report.owner_name || 'Owner')} · ${esc(report.place)}${looks ? ` · ${looks}` : ''}</p>${facts}</div></div>${showNext ? `<p class="next-step">${esc(desk.next)}</p>` : ''}<div class="row-actions">${desk.wait}${desk.primary}${desk.hide}</div></article>`;
}
function lostWork(report) {
  if (report.hidden) return 'hidden';
  if (report.status === 'closed') return 'done';
  const claim = arr('claims').find(item => String(item.report_id) === String(report.id) && item.status !== 'rejected');
  if (claim && claim.status !== 'released') return 'waiting';
  if (matchesFor('report_id', report.id).some(match => match.status === 'confirmed')) return 'waiting';
  return 'need';
}
function sortLost(reports) {
  return [...reports].sort((a, b) => {
    const flag = Number(Boolean(b.flagged && !b.hidden)) - Number(Boolean(a.flagged && !a.hidden));
    if (flag) return flag;
    const match = Number(matchesFor('report_id', b.id).some(row => row.status === 'suggested')) - Number(matchesFor('report_id', a.id).some(row => row.status === 'suggested'));
    if (match) return match;
    return Number(b.id) - Number(a.id);
  });
}
function renderLost() {
  const all = arr('reports');
  const bucket = ['need', 'waiting', 'done'].includes(state.tab.lost) ? state.tab.lost : 'need';
  const scoped = all.filter(inCategory);
  const counts = { need: 0, waiting: 0, done: 0 };
  // Hidden reports sit with the closed ones, tagged Hidden, with a Show again button.
  const group = report => { const work = lostWork(report); return work === 'hidden' ? 'done' : work; };
  scoped.forEach(report => { counts[group(report)] += 1; });
  let reports = state.query.trim() ? scoped : scoped.filter(report => group(report) === bucket);
  reports = sortLost(reports.filter(report => hit([report.description, report.owner_name, report.place, report.status_label, report.category, catName(report.category)])));
  const info = pageOf(reports, 'lost');
  const none = state.query.trim()
    ? ['No reports match', 'Try a different word, or clear the search.']
    : bucket === 'need' ? ['Nothing needs you', 'New reports, guest checks, and unmatched items show here.']
    : bucket === 'waiting' ? ['Nobody is waiting', 'Invited owners and open claims show here.']
    : ['No closed reports yet', 'Handed-back and hidden reports stay here.'];
  const body = info.rows.length ? cardSlide(`<div class="cards desk-list">${info.rows.map(lostCard).join('')}</div>`, pager('lost', info)) : empty(none[0], none[1], 'documents');
  return pageHead('Lost reports', 'Open Action needed first. Check guest reports before matching.')
    + tabs('lost', [['need', 'Action needed', counts.need], ['waiting', 'In progress', counts.waiting], ['done', 'Closed', counts.done]])
    + `<div class="toolbar">${searchBox('Search', 'Search by item, owner, or place')}${categorySelect()}</div>`
    + srHeading('Lost reports') + body;
}
function renderClaims() {
  if (!admin()) return renderMyClaims();
  const quick = state.quick === 'waiting' || state.quick === 'done' ? state.quick : null;
  const mode = quick === 'done' ? 'finished' : quick === 'waiting' ? 'needs' : ['needs', 'finished', 'all'].includes(state.tab.claims) ? state.tab.claims : 'needs';
  const finished = arr('claims').filter(claim => ['released', 'rejected'].includes(claim.status));
  const pool = quick === 'done' ? doneThisWeek() : mode === 'finished' ? finished : mode === 'all' ? [...waitingClaims(), ...finished] : waitingClaims();
  const claims = pool.filter(claim => inCategory({ category: claim.item_category }) && hit([claim.item_description, claim.report_description, claim.claimant_name, claim.claimant_student_number, claim.status_label, claim.item_category]));
  const info = pageOf(claims, 'claims');
  const none = quick === 'done' ? ['Nothing done this week yet', 'Items you hand back show up here for 7 days.']
    : mode === 'finished' ? ['Nothing finished yet', 'Handed back and rejected claims are listed here.']
    : mode === 'all' ? ['No claims yet', 'Claims show up here after an owner answers the questions.']
    : ['Nothing is waiting', 'New claims show up here after an owner answers the questions. You can also look at matches.'];
  const body = info.rows.length
    ? cardSlide(`<div class="cards desk-list">${info.rows.map(claimCard).join('')}</div>`, pager('claims', info))
    : empty(none[0], none[1], 'shield', mode === 'needs' ? navButton('View matches', 'matches', 'primary') : '');
  const head = quick ? pageHead(QUICK[quick].title, QUICK[quick].text) : pageHead('Claims', 'Verify ownership answers and a valid ID before handover. Most urgent first.');
  return head
    + (quick ? filterChip(QUICK[quick].title, claims.length, 'claim') : tabs('claims', [['needs', 'Pending', waitingClaims().length], ['finished', 'Completed', finished.length]]))
    + `<div class="toolbar">${searchBox('Search', 'Search by item or person')}${categorySelect()}</div>`
    + srHeading(mode === 'finished' ? 'Finished claims' : 'Claims to check') + body;
}
function renderMyClaims() {
  const invites = claimableInvites();
  const claims = arr('claims');
  const progress = claims.filter(claim => !['released', 'rejected'].includes(claim.status));
  const returned = claims.filter(claim => claim.status === 'released');
  const rejected = claims.filter(claim => claim.status === 'rejected');
  const allowed = ['invites', 'progress', 'returned'].concat(rejected.length ? ['rejected'] : []);
  const mode = allowed.includes(state.tab.myclaims) ? state.tab.myclaims : 'invites';
  state.tab.myclaims = mode;
  const heads = {
    invites: ['Invitations', 'Matches CSA confirmed. Answer the questions on a card to claim your item, then bring a valid ID to the office.'],
    progress: ['Claims in progress', 'Claims you already sent. They stay here until CSA hands the item back. Bring your ID when the office asks.'],
    returned: ['Returned', 'Items CSA already handed back to you.'],
    rejected: ['Not approved', 'Claims that were not approved. Read the reason, then ask CSA if you can try again.']
  };
  const [title, blurb] = heads[mode];
  const tabItems = [['invites', 'Invitations', invites.length], ['progress', 'In progress', progress.length], ['returned', 'Returned', returned.length]];
  if (rejected.length) tabItems.push(['rejected', 'Not approved', rejected.length]);
  const inviteHtml = invites.map(match => {
    const open = match.can_claim !== false;
    const action = open ? button('Claim item', 'claim', match.id, 'primary') : disabledButton('Claim item', match.eligibility_note || 'This invitation is not open right now.');
    return `<article class="claim"><div class="claim-main"><span class="item-icon" aria-hidden="true">${catIcon(match.category)}</span><div class="report-copy"><h3>${esc(match.report_description || 'Your report')}</h3><p class="meta">${esc(catName(match.category))} at the CSA office</p><p class="meta">Answer the questions to claim this item.</p>${tracker({ invite: match })}</div></div><div class="claim-actions">${action}</div></article>`;
  }).join('');
  const rows = { invites: inviteHtml, progress: progress.map(claimCard).join(''), returned: returned.map(claimCard).join(''), rejected: rejected.map(claimCard).join('') };
  const emptyCopy = {
    invites: ['No invitations yet', 'When CSA confirms a match, answer the questions here to claim it.', 'match', navButton('My reports', 'reports')],
    progress: ['No claims in progress', 'After you answer the questions, the claim stays here until pickup.', 'shield', ''],
    returned: ['Nothing handed back yet', 'Items you already picked up are listed here.', 'check', ''],
    rejected: ['No declined claims', 'Claims that are not approved show up here.', 'shield', '']
  };
  const none = emptyCopy[mode];
  const body = rows[mode] || empty(none[0], none[1], none[2], none[3]);
  return pageHead(title, blurb)
    + '<p class="note" role="note">To get an item back, answer the ownership questions correctly and show a valid ID at the CSA office. Photos and the exact place of found items stay private.</p>'
    + tabs('myclaims', tabItems)
    + srHeading(title)
    + `<div class="cards">${body}</div>`;
}
function matchLabel(match) {
  return `${match.level === 'strong' ? 'Strong' : 'Possible'} match ${Math.round(Number(match.score) || 0)}%`;
}
function matchWhy(match) {
  const details = match.score_details || {};
  const ai = details.method && details.method !== 'typed_details';
  let list = '';
  const rich = Array.isArray(details.reasons) && details.reasons.length && details.reasons[0].key;
  if (rich) {
    list = `<ul class="why-signals">${details.reasons.map(reason => {
      const max = Number(reason.max) || 0;
      const points = Number(reason.points) || 0;
      const width = max ? Math.max(0, Math.min(100, Math.round(100 * points / max))) : 0;
      const used = reason.state !== 'unknown';
      const num = value => Number.isInteger(value) ? String(value) : value.toFixed(1);
      const score = used ? `${num(points)}/${num(max)}` : '—';
      const explain = used && width < 100 && reason.text ? `<small>${esc(reason.text)}</small>` : '';
      return `<li class="sig ${esc(reason.state || '')}"><span class="sig-name">${esc(reason.label)}</span><span class="sig-bar" aria-hidden="true"><i style="width:${width}%"></i></span><span class="sig-points">${score}</span>${explain}</li>`;
    }).join('')}</ul>`;
  } else if (Array.isArray(details.reasons) && details.reasons.length) {
    list = `<ul class="why-list">${details.reasons.map(reason => `<li class="${reason.ok ? 'ok' : 'no'}">${svg(reason.ok ? 'check' : 'cross')}<span>${esc(reason.text)}</span></li>`).join('')}</ul>`;
  } else {
    list = '<p class="meta">Press Find matches to see the reasons for this pair.</p>';
  }
  const caps = Array.isArray(details.caps) && details.caps.length ? `<div class="why-caps"><strong>Why the score is not higher</strong><ul>${details.caps.map(text => `<li>${esc(text)}</li>`).join('')}</ul></div>` : '';
  const similar=details.similar_candidates?'<p class="note"><strong>Similar candidates</strong> · Other items scored within six points. Compare unique details before confirming.</p>':'';
  const extra = details.note ? `<p class="meta">${esc(details.note)}</p>` : '';
  const note = details.method === 'gemini_ai'
    ? 'Google Gemini compared the photos and descriptions.'
    : ai ? 'The available local models compared the photos and descriptions.' : 'AI was off, so only the typed details were compared.';
  return `<details class="fold"><summary>Why this match?</summary>${similar}${list}${caps}${extra}<p class="meta">${note} Strong starts at 60. Possible starts at 40. Strong also needs agreement across clues. A score is a hint, not proof.</p></details>`;
}
function matchCard(match) {
  const ai = match.method && match.method !== 'typed_details';
  const photo = (id, label) => id ? `<figure class="photo-box"><img src="/api/files/${encodeURIComponent(id)}" alt="${esc(label)}, visible to staff only"><figcaption>${esc(label)}</figcaption></figure>` : '';
  const photos = match.report_photo_id || match.item_photo_id ? `<div class="photo-pair">${photo(match.report_photo_id, 'Owner’s photo')}${photo(match.item_photo_id, 'Item in the office')}</div>` : '';
  let actions = '';
  let next = '';
  const needsCheck = match.status === 'suggested' && match.report_flagged;
  const guestTag = match.owner_role === 'guest' ? ' <span class="tag">Guest</span>' : '';
  if (needsCheck) {
    actions = button('Check report', 'check-report', match.report_id, 'primary') + moreMenu([['Reject', 'dismiss-match', match.id, true], ['View item', 'view-item', match.item_id]]);
    next = 'A guest sent this report. Check it first, then you can approve the match.';
  } else if (match.status === 'suggested') {
    actions = button('Approve match', 'confirm-match', match.id, 'primary') + moreMenu([['Reject', 'dismiss-match', match.id, true], ['View item', 'view-item', match.item_id]]);
    next = 'Approve to invite the owner to answer questions, or Reject if it is not the same item.';
  } else {
    actions = '<span class="waiting-tag">Waiting for the owner</span>' + moreMenu([['View item', 'view-item', match.item_id]]);
    next = 'The owner answers the questions. Their claim shows up in Claims.';
  }
  const showNext = needsCheck;
  return `<article class="record match-card${state.taskKey === `match:${match.id}` ? ' is-focus' : ''}" id="match-${esc(match.id)}"><div class="match-head"><div><h3>${esc(match.item_description || 'Item')}</h3><p class="meta">Owner: ${esc(match.owner_name || 'Owner')}${guestTag} · ${esc(match.report_description || '')}</p></div><div class="match-score"><span class="score-pill ${match.level === 'strong' ? 'strong' : 'possible'}">${matchLabel(match)}</span><span class="badge ${ai ? 'ai' : 'good'}">${svg(ai ? 'spark' : 'check')}<span>${ai ? 'AI-assisted' : 'Typed details'}</span></span></div></div>${photos}${matchWhy(match)}${showNext ? `<p class="next-step">${esc(next)}</p>` : ''}<div class="row-actions">${actions}</div></article>`;
}
function renderMatches() {
  const quick = state.quick === 'matches';
  const mode = quick ? 'review' : ['review', 'invited'].includes(state.tab.matches) ? state.tab.matches : 'review';
  const wanted = mode === 'invited' ? ['confirmed'] : ['suggested'];
  const pool = state.query.trim()
    ? arr('matches').filter(inCategory)
    : arr('matches').filter(match => wanted.includes(match.status) && inCategory(match));
  const matches = [...pool].filter(match => hit([match.item_description, match.report_description, match.owner_name, match.category])).sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0) || Number(b.id) - Number(a.id));
  const reviewCount = arr('matches').filter(match => match.status === 'suggested' && inCategory(match)).length;
  const invitedCount = arr('matches').filter(match => match.status === 'confirmed' && inCategory(match)).length;
  const info = pageOf(matches, 'matches');
  const body = info.rows.length
    ? cardSlide(`<div class="cards desk-list">${info.rows.map(matchCard).join('')}</div>`, pager('matches', info))
    : empty(mode === 'invited' ? 'Nobody is waiting' : mode === 'all' ? 'No matches yet' : 'Nothing needs a decision', mode === 'invited' ? 'Approved matches stay here until the owner answers.' : 'Find matches after a new report or item arrives.', 'search', mode === 'invited' ? '' : button('Find matches', 'run-matching', '', 'primary'));
  const head = quick ? pageHead(QUICK.matches.title, QUICK.matches.text, button('Find matches', 'run-matching', '', 'secondary'))
    : pageHead('Matches', 'Compare paired lost reports and office items, then approve to invite the owner.', button('Find matches', 'run-matching', '', 'primary'));
  const aiOff = state.data.matching_status?.ready ? '' : aiStatus();
  return head + aiOff
    + (quick ? filterChip(QUICK.matches.title, matches.length, 'match') : tabs('matches', [['review', 'Needs a decision', reviewCount], ['invited', 'Waiting for the owner', invitedCount]]))
    + `<div class="toolbar">${searchBox('Search', 'Search by item or owner')}${categorySelect()}</div>`
    + srHeading(mode === 'invited' ? 'Waiting for the owner' : 'Needs a decision') + body;
}
function cleanupCandidates() {
  return arr('items').filter(item => item.status === 'available' && !item.active_claims && daysAgo(item.received_at) >= Number(item.unclaimed_after_days || 30));
}
function officeOuter(tab) {
  const current = tab === 'maintenance'?'maintenance':tab === 'cleanup' ? 'cleanup' : tab === 'staff' ? 'staff' : 'records';
  const items = [['staff', 'Staff'], ['records', 'Records'], ['cleanup', 'Clean up'],['maintenance','Maintenance']];
  return `<div class="tabs" role="tablist">${items.map(([key, label]) => {
    const on = current === key;
    return `<button class="tab" type="button" role="tab" data-action="office-tab" data-id="${key}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${label}</button>`;
  }).join('')}</div>`;
}
function officeLists(tab) {
  const items = [['roster', 'Allowed emails'], ['people', 'People'], ['activity', 'Logs']];
  return `<div class="office-switch" role="group" aria-label="Records">${items.map(([key, label]) => {
    const on = tab === key;
    return `<button class="btn ${on ? 'primary' : 'secondary'} sm" type="button" data-action="office-list" data-id="${key}" aria-pressed="${on}">${label}</button>`;
  }).join('')}</div>`;
}
function officePulse() {
  const staffN = arr('staff').filter(person => person.active !== false).length;
  const allowed = arr('roster').filter(row => row.active).length;
  const blocked = arr('people').filter(person => person.blocked).length;
  const old = cleanupCandidates().length;
  const item = (action, id, icon, label, count, hint) => `<button class="stat stat-link${count ? '' : ' is-zero'}" type="button" data-action="${action}" data-id="${id}"><span class="stat-icon" aria-hidden="true">${svg(icon)}</span><div><span>${label}</span><strong>${count}</strong><small>${hint}</small></div></button>`;
  return `<div class="stats office-pulse" aria-label="Administration summary">${item('office-tab', 'staff', 'user', 'Staff', staffN, staffN ? 'Can use the desk' : 'None active')}${item('office-list', 'roster', 'mail', 'Allowed emails', allowed, allowed ? 'Can sign in' : 'List is empty')}${item('office-list', 'people', 'shield', 'Blocked', blocked, blocked ? 'Cannot sign in' : 'Nobody blocked')}${item('office-tab', 'cleanup', 'clock', 'To clean up', old, old ? 'Past keep time' : 'None waiting')}</div>`;
}
function renderOffice() {
  if(state.tab.office==='maintenance')return renderMaintenance();
  const tab = ['staff', 'roster', 'people', 'activity', 'cleanup','maintenance'].includes(state.tab.office) ? state.tab.office : 'staff';
  const heads = { staff: button('Add staff', 'add-staff', '', 'primary'), roster: `${button('Import CSV', 'import-roster', '', 'secondary')}${button('Add email', 'add-roster', '', 'primary')}` };
  const blurbs = {
    staff: 'Who can use this desk. Add a person, or edit their name and password.',
    roster: 'School emails that may sign in, and whether each person is a student or a professor.',
    people: 'Everyone with an account. Block someone who sends spam. Their reports stay, and the block is written in the log.',
    cleanup: 'Items past their keep time, with nobody checking them. Clean up marks them Not claimed.',
    activity: 'Sign-ins, checks, and handovers. This log cannot be edited.'
  };
  const head = pageHead('Administration', blurbs[tab] || blurbs.staff, heads[tab] || '');
  const pulse = officePulse();
  const nav = officeOuter(tab);
  const lists = ['roster', 'people', 'activity'].includes(tab) ? officeLists(tab) : '';
  const top = head + pulse + nav + lists;
  if (tab === 'staff') {
    const rows = arr('staff').map(person => {
      const you = String(person.email || '').toLowerCase() === String(state.user.email || '').toLowerCase() ? ' <span class="tag">You</span>' : '';
      return `<tr><td><strong>${esc(person.name)}</strong>${you}</td><td>${esc(person.email)}</td><td>${badge({ status: person.active ? 'active' : 'inactive', status_label: person.active ? 'Active' : 'Inactive' })}</td><td>${button('Edit', 'edit-staff', person.id, 'secondary sm')}</td></tr>`;
    }).join('');
    return top + srHeading('Staff accounts') + (rows ? `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Access</th><th><span class="sr-only">Action</span></th></tr></thead><tbody>${rows}</tbody></table></div>` : empty('No staff yet', 'Add a CSA account to share the desk.', 'audit', button('Add staff', 'add-staff', '', 'primary')));
  }
  if (tab === 'roster') {
    const all = arr('roster');
    const domains = (state.config.school_domains || []).map(d => `@${d}`).join(', ') || 'the school domain';
    const rule = state.config.demo_mode
      ? `Any school email can sign in. This list is optional: add someone to set their role (student or professor). In live mode, a non-empty list becomes the only people who can sign in.`
      : all.length
      ? `Only the emails below can sign in with a school email code. Switch one off to stop it without deleting it. Their role comes from this list.`
      : `The list is empty, so any address ending in ${esc(domains)} can sign in as a student. Add emails to limit sign-in to the people you list.`;
    const list = all.filter(row => hit([row.email, row.name, row.student_number, row.role]));
    const info = pageOf(list, 'roster', 10);
    const rows = info.rows.map(row => `<tr><td><strong>${esc(row.email)}</strong></td><td>${esc(row.name || '')}</td><td>${esc(row.student_number || '')}</td><td>${row.role === 'professor' ? 'Professor' : 'Student'}</td><td>${badge({ status: row.active ? 'active' : 'inactive', status_label: row.active ? 'Allowed' : 'Switched off' })}</td><td><div class="row-actions">${button(row.active ? 'Switch off' : 'Switch on', 'toggle-roster', row.id, 'secondary sm')}${button('Remove', 'remove-roster', row.id, 'secondary sm')}</div></td></tr>`).join('');
    return top + `<div class="note" role="note"><p>${rule}</p><p>CSV columns: email, name, student_number, role.</p></div><div class="toolbar">${searchBox('Search', 'Search by email, name, or number')}</div>${srHeading('Allowed school emails')}`
      + (rows ? `<div class="table-wrap"><table><thead><tr><th>Email</th><th>Name</th><th>Number</th><th>Role</th><th>Status</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>${rows}</tbody></table></div>${pager('roster', info)}` : empty(all.length ? 'No match' : 'No allowed emails yet', all.length ? 'Try a different search.' : 'Add emails one by one, or import a CSV file.', 'audit', all.length ? '' : button('Add email', 'add-roster', '', 'primary')));
  }
  if (tab === 'people') {
    const list = arr('people').filter(person => hit([person.name, person.email, person.phone, person.student_number, person.role]));
    const info = pageOf(list, 'people', 10);
    const roleName = { student: 'Student', professor: 'Professor', guest: 'Guest', admin: 'Staff' };
    const rows = info.rows.map(person => {
      const status = person.blocked ? badge({ status: 'inactive', status_label: 'Blocked' }) : person.email_verified === 0 ? badge({ status: 'pending', status_label: 'Not confirmed' }) : badge({ status: 'active', status_label: 'Active' });
      const setPw = person.role === 'admin' ? '' : button('Set password', 'set-person-password', person.id, 'secondary sm');
      const block = person.role === 'admin' ? '' : person.blocked ? button('Unblock', 'unblock-user', person.id, 'secondary sm') : button('Block', 'block-user', person.id, 'secondary sm');
      return `<tr><td><strong>${esc(person.name)}</strong><br><span class="meta">${esc(person.email)}${person.student_number ? ` · ${esc(person.student_number)}` : ''}${person.phone ? ` · ${esc(person.phone)}` : ''}</span></td><td>${roleName[person.role] || esc(person.role)}</td><td>${Number(person.reports || 0)}</td><td>${Number(person.claims || 0)}</td><td>${status}${person.blocked_reason ? `<br><span class="meta">${esc(person.blocked_reason)}</span>` : ''}</td><td><div class="row-actions">${setPw}${block}</div></td></tr>`;
    }).join('');
    return top + `<p class="note" role="note">Set password only after the person shows a valid ID at the desk. LyFind does not email the new password. Block an account that sends spam or pranks. They are signed out and cannot sign in. Their records stay, and every block is written in the activity log.</p><div class="toolbar">${searchBox('Search', 'Search by name or email')}</div>${srHeading('People')}`
      + (rows ? `<div class="table-wrap"><table><thead><tr><th>Person</th><th>Role</th><th>Reports</th><th>Claims</th><th>Status</th><th><span class="sr-only">Action</span></th></tr></thead><tbody>${rows}</tbody></table></div>${pager('people', info)}` : empty('No people found', 'Try a different search.', 'audit'));
  }
  if (tab === 'cleanup') {
    const old = cleanupCandidates();
    const rows = old.map(item => `<div class="list-row"><span class="icon-tile sm" aria-hidden="true">${catIcon(item.category)}</span><div class="grow"><strong>${esc(item.description)}</strong><p class="meta">${esc(item.place)} · Kept ${Math.floor(daysAgo(item.received_at))} days · Keep time ${esc(item.unclaimed_after_days || 30)} days</p>${dateLine(item.date_found, 'Date found')}${dateLine(item.received_at, 'Received')}</div>${button('View item', 'open-item', item.id, 'secondary sm')}</div>`).join('');
    return top + srHeading('Clean up old items') + `<section class="card" aria-labelledby="clean-h"><div class="card-head"><h2 id="clean-h">Items kept too long</h2>${old.length ? button('Clean up', 'expire', '', 'primary') : ''}</div><p class="muted">Open an item to read it first. Clean up marks every item in this list Not claimed. It does not delete the record.</p>${rows ? `<div class="list">${rows}</div>` : empty('Nothing to clean up', 'No item is past its keep time yet.', 'check')}</section>`;
  }
  const logs = arr('audit').filter(entry => hit([entry.action, entry.detail, entry.actor_name, entry.details]));
  const info = pageOf(logs, 'office');
  const rows = info.rows.map(entry => `<tr><td>${esc(dateText(entry.created_at || entry.timestamp))}</td><td>${esc(entry.actor_name || 'System')}</td><td>${esc(actionText(entry.action))}</td><td>${esc(entry.detail || entry.details || '')}</td></tr>`).join('');
  return top + `<p class="note" role="note">This log cannot be edited. Search a name or an action, such as “handed” or “blocked”.</p><div class="toolbar">${searchBox('Search', 'Search the log')}</div>${srHeading('Logs')}`
    + (rows ? `<div class="table-wrap"><table><thead><tr><th>When</th><th>Who</th><th>What</th><th>Detail</th></tr></thead><tbody>${rows}</tbody></table></div>${pager('office', info)}` : empty('No activity yet', 'Sign-ins, checks, and handovers will be listed here.', 'activity'));
}
function staffInbox() {
  const rows = [];
  arr('reports').filter(report => report.flagged && !report.hidden).forEach(report => {
    rows.push({ tone: 'wait', word: 'Needs you', title: report.description, text: `${report.owner_name || 'A guest'} sent this report. Check it before matching starts.`, view: 'lost', label: 'Check report', at: report.created_at });
  });
  waitingClaims().forEach(claim => {
    const ready = claim.status === 'approved' || claim.status === 'verified';
    rows.push({ tone: ready ? 'good' : 'wait', word: ready ? 'Ready' : 'Needs you', title: claimTitle(claim), text: `${claim.claimant_name || 'Owner'}. ${nextForClaim(claim)}`, view: 'claims', label: 'Open claim', at: claim.created_at });
  });
  arr('matches').filter(match => match.status === 'suggested').forEach(match => {
    rows.push({ tone: 'wait', word: 'Needs you', title: match.item_description || 'Item', text: `${match.owner_name || 'Owner'} may own this. ${matchLabel(match)}. Approve to invite the owner, or reject it.`, view: 'matches', label: 'Review match', at: match.created_at });
  });
  return rows;
}
function noteTone(message) {
  const text = String(message || '').toLowerCase();
  if (text.includes('not approved')) return 'bad';
  if (text.includes('handed back') || text.includes('approved') || text.includes('passed') || text.includes('checked') || text.includes('received')) return 'good';
  return 'wait';
}
function noticeWord(tone, message) {
  if (tone === 'good') return 'Ready';
  if (tone === 'bad') return 'Not approved';
  const text = String(message || '').toLowerCase();
  if (text.includes('possible match') || text.includes('answer a few questions')) return 'Needs you';
  return 'Waiting';
}
function noteTitle(message) {
  const text = String(message || '').toLowerCase();
  if (text.includes('not approved')) return 'Not approved';
  if (text.includes('handed back')) return 'Item handed back';
  if (text.includes('approved')) return 'Ready to pick up';
  if (text.includes('both checks')) return 'Checks passed';
  if (text.includes('online check')) return 'Bring your ID';
  if (text.includes('possible match')) return 'You may have a match';
  if (text.includes('checked your lost report')) return 'Report checked';
  if (text.includes('received the item')) return 'Item received';
  if (text.includes('saved a lost report')) return 'Report saved at the desk';
  return 'Update';
}
function noteTarget(note) {
  if (note.claim_id) return ['claims', 'Open claim'];
  if (note.report_id) return ['reports', 'Open report'];
  return ['home', 'Dashboard'];
}
function noticeStamp(value) {
  const info = dateInfo(value);
  return info ? `${info.weekday}, ${info.shortDate}` : '';
}
function noticeBucket(value) {
  const parsed = parseDay(value);
  if (!parsed) return { key: 'none', label: 'No date', order: -1 };
  const now = new Date();
  const start = date => new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const todayStart = start(now);
  const day = start(parsed);
  const days = Math.round((todayStart - day) / 86400000);
  const monday = date => { const copy = start(date); copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7)); return copy; };
  if (days <= 0) return { key: 'd:' + dayKey(day), label: 'Today', order: day.getTime() };
  if (days === 1) return { key: 'd:' + dayKey(day), label: 'Yesterday', order: day.getTime() };
  if (day >= monday(now)) return { key: 'd:' + dayKey(day), label: noticeStamp(value), order: day.getTime() };
  const week = monday(day);
  const ageWeeks = Math.round((monday(now) - week) / (7 * 86400000));
  if (ageWeeks > 0 && ageWeeks <= 4) {
    const end = new Date(week); end.setDate(week.getDate() + 6);
    const span = week.getMonth() === end.getMonth()
      ? `${week.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}–${end.getDate()}`
      : `${week.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}–${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
    return { key: 'w:' + dayKey(week), label: `Week of ${week.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`, hint: span, order: week.getTime() };
  }
  if (day.getFullYear() === now.getFullYear()) {
    const month = new Date(day.getFullYear(), day.getMonth(), 1);
    return { key: 'm:' + dayKey(month), label: month.toLocaleDateString('en-US', { month: 'long' }), order: month.getTime() };
  }
  return { key: 'y:' + day.getFullYear(), label: String(day.getFullYear()), order: new Date(day.getFullYear(), 0, 1).getTime() };
}
function noticeList(rows) {
  const sorted = [...rows].sort((a, b) => (parseDay(b.at)?.getTime() || 0) - (parseDay(a.at)?.getTime() || 0));
  const groups = new Map();
  sorted.forEach(row => {
    const bucket = noticeBucket(row.at);
    if (!groups.has(bucket.key)) groups.set(bucket.key, { ...bucket, rows: [] });
    groups.get(bucket.key).rows.push(row);
  });
  return [...groups.values()].sort((a, b) => b.order - a.order).map(group => `<section class="notice-group" aria-label="${esc(group.label)}"><h3 class="notice-group-title">${esc(group.label)}${group.hint ? `<span class="notice-span">${esc(group.hint)}</span>` : ''}<span class="tag">${group.rows.length}</span></h3>${group.rows.map(row => noticeCard({ ...row, when: noticeStamp(row.at) })).join('')}</section>`).join('');
}
function noticeKey() {
  return `<p class="notice-key">The line on the side: <span class="is-good">Ready</span> means done. <span class="is-wait">Waiting</span> means still in progress. <span class="is-wait">Needs you</span> means it is your turn. <span class="is-bad">Not approved</span> means it stopped.</p>`;
}
function noticeCard(row) {
  const go = row.view ? navButton(row.label, row.view, 'secondary sm') : '';
  const when = row.when ? `<time class="notice-when">${esc(row.when)}</time>` : '';
  const word = row.word || noticeWord(row.tone, row.text);
  return `<article class="notice ${row.tone || 'wait'}"><div class="grow"><p class="notice-mark">${esc(word)}</p><h3>${esc(row.title || 'Update')}</h3>${row.text ? `<p class="notice-text">${esc(row.text)}</p>` : ''}</div>${when}${go}</article>`;
}
function renderAccount() {
  const person = state.user;
  const fromEmail = studentNumberFrom(person.email);
  const idLabel = person.role === 'guest' ? '' : admin() ? 'Staff number' : person.role === 'professor' ? 'Employee number' : 'Student number';
  const idHint = fromEmail ? 'Filled in from your LPU email. You never need to type it.' : 'Add it once and CSA will not ask again.';
  const numberField = idLabel ? field('student_number', idLabel, 'text', { maxlength: 40, value: fromEmail || person.student_number || '', readonly: Boolean(fromEmail), hint: idHint }) : '';
  const saved = state.flash?.view === 'account' ? `<p class="save-banner" role="status">${statusMarkup(state.flash.text, 'ok')}</p>` : '';
  const role = admin() ? 'CSA staff' : person.role === 'professor' ? 'Professor' : person.role === 'guest' ? 'Guest' : 'Student';
  return `<div class="page-stack">${pageHead('Account', 'Your name, how you sign in, and how this device looks.')}${saved}
    <section class="card profile-card" aria-label="Your profile"><span class="greet-avatar" aria-hidden="true">${esc(initials())}</span><div class="grow"><h2>${esc(person.name)}</h2><p class="meta">${role} · ${esc(person.email)}</p>${fromEmail ? `<p class="meta">${esc(fromEmail)}</p>` : ''}${person.phone ? `<p class="meta">${esc(person.phone)}</p>` : ''}</div><div class="profile-tools"><p class="form-kicker">Appearance</p><div class="theme-switch" role="group" aria-label="Appearance"><button type="button" data-action="set-theme" data-theme="light" aria-pressed="${readTheme() === 'light'}">Light</button><button type="button" data-action="set-theme" data-theme="dark" aria-pressed="${readTheme() === 'dark'}">Dark</button></div><p class="meta">Saved on this device only.</p></div></section>
    <section class="card" aria-labelledby="acc-h"><h2 id="acc-h">Your details</h2>
      <form data-form="account" novalidate>
        <p class="form-kicker">Name</p>
        <div class="name-grid">
          ${field('first_name', 'First name', 'text', { required: true, maxlength: 40, value: person.first_name || '', autocomplete: 'given-name' })}
          ${field('middle_name', 'Middle name', 'text', { maxlength: 40, value: person.middle_name || '', autocomplete: 'additional-name' })}
          ${field('last_name', 'Last name', 'text', { required: true, maxlength: 40, value: person.last_name || '', autocomplete: 'family-name' })}
          ${field('suffix', 'Suffix', 'text', { maxlength: 12, value: person.suffix || '', placeholder: 'Jr., III', autocomplete: 'honorific-suffix' })}
        </div>
        ${field('email', 'Email', 'email', { value: person.email || '', required: true, readonly: true, hint: 'Your email cannot be changed.' })}
        <p class="form-kicker">${person.role === 'guest' ? 'Contact (optional)' : 'Contact and ID (optional)'}</p>
        <p class="muted">Saved once, so staff never retype them when you claim an item.</p>
        ${field('phone', 'Phone', 'tel', { maxlength: 20, value: person.phone || '', placeholder: '0917 123 4567', autocomplete: 'tel', inputmode: 'tel', hint: 'Used only to reach you about your item.' })}
        ${numberField}
        <button class="btn primary" type="submit">Save changes</button>
      </form>
    </section>
    ${person.role==='guest'?'':`<section class="card" aria-labelledby="acc-pw"><h2 id="acc-pw">Password</h2>
      <p class="muted">Press Set new password if you still know the one you use now. If you forgot it, LyFind cannot email a new one.</p>
      <div class="password-choices">${button('Set new password', 'show-password', '', 'secondary')}${button('Forgot your password?', 'forgot-password', '', 'secondary')}</div>
      <form id="password-form" data-form="set-password" novalidate hidden>
        ${passwordInput('current_password', 'Current password', 'current-password', 'Enter your current password')}
        ${passwordSet(PW_MIN, true)}
        <button class="btn primary" type="submit">Set new password</button>
      </form>
      <div class="note" role="note" id="forgot-note" hidden>${admin() ? '<p>You are still signed in, so you do not need the old password. Open Staff, press Edit next to your name, and type the new password there.</p>' + button('Open Staff', 'open-staff', '', 'secondary sm') : '<p>Visit the CSA office with a valid ID. Staff will set a new password. LyFind cannot email one.</p>'}</div>
    </section>
    `}
    <section class="card account-session" aria-labelledby="acc-out"><div><h2 id="acc-out">This sign-in</h2><p class="muted">Switch account opens Login for a different email. Sign out returns you to the welcome page.</p></div><div class="account-session-actions">${button('Switch account', 'switch-account', '', 'secondary')}${button('Sign out', 'logout', '', 'primary')}</div></section>
  </div>`;
}
function renderUpdates() {
  if (!admin()) {
    const source = journey();
    const banner = journeyTitle(source) ? `<section class="panel" aria-labelledby="upd-now"><h2 id="upd-now">${esc(journeyTitle(source))}</h2>${tracker(source, true)}<p class="next-line">${esc(trackerModel(source).line)}</p></section>` : '';
    const notes = arr('notifications');
    const list = notes.length ? noticeKey() + noticeList(notes.map(note => {
      const [view, label] = noteTarget(note);
      const text = note.message || note.body || '';
      const tone = noteTone(text);
      return { tone, word: noticeWord(tone, text), title: noteTitle(text), text, at: note.created_at, view, label };
    })) : empty('No notifications', 'CSA will write here when there is news about your item.', 'notices', navButton('Dashboard', 'home'));
    return `<div class="page-stack">${pageHead('Notifications', 'Messages from CSA about your reports and claims. Newest first. Older messages are grouped by week, month, or year.')}${banner}<section class="panel" aria-labelledby="upd-msgs"><h2 id="upd-msgs" class="sr-only">Messages from CSA</h2>${list}</section></div>`;
  }
  const rows = staffInbox();
  const list = rows.length
    ? noticeKey() + noticeList(rows)
    : empty('Nothing needs you', 'Lost reports, found items, matches, and claims show up here when they need a decision.', 'check', navButton('Dashboard', 'today'));
  return `<div class="page-stack">${pageHead('Notifications', 'Guest reports to check, matches to review, and claims that are waiting. Newest first.')}<section class="panel" aria-labelledby="upd-msgs"><h2 id="upd-msgs" class="sr-only">Desk notifications</h2>${list}</section></div>`;
}
function renderView() {
  if (state.view === 'help') return helpContent();
  if (state.view === 'account') return renderAccount();
  if (admin()) {
    if (state.view === 'matches') return renderMatches();
    if (state.view === 'lost') return renderLost();
    if (state.view === 'items') return renderItems();
    if (state.view === 'claims') return renderClaims();
    if (state.view === 'office') return renderOffice();
    if (state.view === 'updates') return renderUpdates();
    return renderToday();
  }
  if (state.view === 'board' && state.user.role !== 'guest') return renderFoundBoard();
  if (state.view === 'reports') return renderReports();
  if (state.view === 'claims') return renderMyClaims();
  if (state.view === 'updates') return renderUpdates();
  return renderHome();
}
function shell() {
  const items = navItems();
  if (!items.some(([key]) => key === state.view) && state.view !== 'help') state.view = items[0][0];
  const current = state.view === 'help' ? 'Help' : items.find(([key]) => key === state.view)?.[1] || 'Dashboard';
  const counts = navCounts();
  const link = (key, label, icon) => `<button class="nav-item ${navOn(key) ? 'active' : ''}" type="button" data-nav="${key}" ${navOn(key) ? 'aria-current="page"' : ''}><span aria-hidden="true">${svg(icon)}</span><span>${label}</span>${counts[key] ? `<span class="nav-count"><span class="sr-only">${counts[key]} waiting</span><span aria-hidden="true">${counts[key]}</span></span>` : ''}</button>`;
  const topLink = (key, label) => `<button class="nav-item area-nav-link ${navOn(key) ? 'active' : ''}" type="button" data-nav="${key}" ${navOn(key) ? 'aria-current="page"' : ''}><span>${label}</span>${counts[key] ? `<span class="nav-count"><span class="sr-only">${counts[key]} waiting</span><span aria-hidden="true">${counts[key]}</span></span>` : ''}</button>`;
  const groups = navGroups();
  const nav = groups.map(([label, group], index) => {
    const gap = index ? '<span class="nav-gap" aria-hidden="true"></span>' : '';
    const heading = label ? `<p class="nav-label">${label}</p>` : '';
    const list = group.map(([key, name, icon]) => link(key, name, icon)).join('');
    const help = index === groups.length - 1 ? link('help', 'Help', 'help') : '';
    return `${gap}${heading}${list}${help}`;
  }).join('');
  const topNavItems = [...items.filter(([key]) => key !== 'account'), ['help', 'Help']].map(([key, name]) => topLink(key, name)).join('');
  const role = admin() ? 'CSA staff' : (state.user.role === 'professor' ? 'Professor' : state.user.role === 'guest' ? 'Guest' : 'Student');
  const who = personLine();
  const onHome = state.view === 'home' || state.view === 'today';
  const primaryTopAction = admin()
    ? button('Receive item', 'receive', '', 'primary sm area-top-cta')
    : button('Report lost', 'lost', '', 'primary sm area-top-cta');
  const topbar = `<header class="topbar area-app-nav"><div class="topbar-inner"><button class="menu-button" type="button" data-action="menu" aria-label="Open menu" title="Open menu" aria-controls="sidebar" aria-expanded="false">${svg('menu')}</button><button class="wordmark top-wordmark wh1128-wordmark" type="button" data-action="home" aria-label="LyFind home"><span class="logo-mark">${LOGO}</span><span>LYFIND</span></button><p class="topbar-title" ${onHome ? 'hidden' : ''}>${esc(current)}</p><nav class="area-topnav" aria-label="Primary navigation">${topNavItems}</nav><div class="topbar-actions">${primaryTopAction}<button class="who" type="button" data-nav="account" title="Account"><span class="who-name">${esc(who.name.toUpperCase())}</span><span class="who-meta">${esc(who.meta)}</span></button><button class="top-avatar" type="button" data-nav="account" title="Account · ${esc(state.user.name)}" aria-label="Account">${esc(initials())}</button><button class="icon-button top-logout" type="button" data-action="logout" aria-label="Sign out" title="Sign out">${svg('logout')}</button></div></div></header>`;
  const side = `<aside class="sidebar" id="sidebar"><div class="drawer-head"><button class="wordmark wh1128-wordmark" type="button" data-action="home" aria-label="LyFind home"><span class="logo-mark">${LOGO}</span><span>LYFIND</span></button><button class="icon-button drawer-close" type="button" data-action="menu-close" aria-label="Close menu" title="Close menu">${svg('close')}</button></div><label class="side-search"><span class="sr-only">Search</span><input class="search-input side-search-input" value="${esc(state.query)}" placeholder="Search" aria-label="Search name, item, or place" autocomplete="off"><span class="side-search-icon" aria-hidden="true">${svg('search')}</span></label><nav class="nav-list" aria-label="Main">${nav}</nav><div class="profile"><button class="profile-link" type="button" data-nav="account" title="${esc(state.user.name)}"><span class="avatar">${esc(initials())}</span><span><span class="profile-name">${esc(state.user.name)}</span><span class="profile-role">${role}</span></span></button><button class="icon-button" type="button" data-action="logout" aria-label="Sign out" title="Sign out">${svg('logout')}</button></div></aside>`;
  return `<div class="app area-shell">${side}<button class="nav-overlay" type="button" data-action="menu-close" aria-label="Close menu" title="Close menu" hidden></button><div class="main-col">${topbar}<main class="main" id="main" tabindex="-1"><div class="content">${pageBody()}</div></main></div></div>`;
}
function pageBody() {
  const banner = state.user.blocked ? '<p class="account-banner">Your account is blocked from new claims. Contact the CSA office.</p>' : '';
  return `${banner}${renderView()}<footer class="footer">LyFind · Campus lost and found</footer>`;
}
function paintChrome() {
  const items = navItems();
  if (!items.some(([key]) => key === state.view) && state.view !== 'help') state.view = items[0][0];
  const current = state.view === 'help' ? 'Help' : items.find(([key]) => key === state.view)?.[1] || 'Dashboard';
  const title = document.querySelector('.topbar-title');
  if (title) { title.textContent = current; title.hidden = state.view === 'home' || state.view === 'today'; }
  const line = state.user ? personLine() : null;
  const whoName = document.querySelector('.who-name');
  const whoMeta = document.querySelector('.who-meta');
  if (line && whoName) whoName.textContent = line.name.toUpperCase();
  if (line && whoMeta) whoMeta.textContent = line.meta;
  const sideSearch = document.querySelector('.side-search-input');
  if (sideSearch && document.activeElement !== sideSearch) sideSearch.value = state.query;
  const counts = navCounts();
  document.querySelectorAll('.nav-item[data-nav]').forEach(btn => {
    const key = btn.dataset.nav;
    const on = navOn(key);
    btn.classList.toggle('active', on);
    if (on) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
    const existing = btn.querySelector('.nav-count');
    const n = counts[key] || 0;
    if (n) {
      const html = `<span class="nav-count"><span class="sr-only">${n} waiting</span><span aria-hidden="true">${n}</span></span>`;
      if (existing) existing.outerHTML = html;
      else btn.insertAdjacentHTML('beforeend', html);
    } else if (existing) existing.remove();
  });
}
function initials() {
  return state.user?.name?.split(' ').filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'U';
}
function render() {
  window.ReuniteSupport?.update(state.user, state.csrf);
  if (!state.user) {
    if (state.screen === 'auth') renderAuth(); else if (state.screen === 'help') renderPublicHelp(); else renderWelcome();
    return;
  }
  const sideTyping = document.activeElement?.classList?.contains('side-search-input');
  if (!sideTyping) closeMenu(false);
  const content = document.querySelector('.app .content');
  if (content) {
    const typingSearch = document.activeElement?.classList?.contains('search-input') && document.activeElement.closest('.toolbar');
    const keepBar = typingSearch ? document.activeElement.closest('.toolbar') : null;
    if (keepBar) keepBar.remove();
    paintChrome();
    content.innerHTML = pageBody();
    const fresh = content.querySelector('.toolbar');
    if (keepBar && fresh) fresh.replaceWith(keepBar);
    finishRender();
    return;
  }
  app.innerHTML = shell();
  finishRender();
}

const STUDENT_EXAMPLE = '@lpunetwork.edu.ph';
const ROLE_GUIDE = [
  ['lpu', 'Students and professors', [`Choose <b>Sign up</b>, then <b>LPU</b>. Use your ${STUDENT_EXAMPLE} email.`, 'Type the code once, then choose a password. Next time, log in with that email and password.', 'Choose <b>Report lost</b> or <b>Report found</b>. Say what it is, where on campus, and when.', 'Your item moves through Reported, Matched, Verified, and Released. Bring a valid ID to pick it up.']],
  ['guest', 'Guest', ['Choose <b>Sign up</b>, then <b>Guest</b>. Use a personal email. We send a code once.', 'Enter the code to continue. You can add your name and optional phone in Account.', 'Choose <b>Report lost</b>. CSA checks guest lost reports first. Bring found items directly to CSA.', 'Your item moves through Reported, Matched, Verified, and Released. Pick-up still needs a valid ID.']]
];
const FAQS = [
  ['I lost something. What do I do?', 'Sign in and choose Report lost. Name the LPU Cavite place, the date, and what it is. That starts at Reported. A possible item moves it to Matched. You answer questions and show your ID (Verified), then CSA hands it over (Released). Your Dashboard and Notifications show each change.'],
  ['I found something. What do I do?', 'Choose Report found. Say what it is, where you found it, and where it is now: with you, with campus security, or left where it was. If you have it, bring it to the CSA office. An item cannot be claimed until it reaches the office.'],
  ['How do I prove it is mine?', 'When CSA invites you, answer a few questions only the owner would know. Then show a valid ID at the office. Photos and the exact place of found items stay private.'],
  ['What do I bring to the office?', 'A valid ID. CSA never hands an item over without one. If you found something, bring the item too.'],
  ['How long are items kept?', 'Most items are kept for 30 days. After that, an unclaimed item is marked as not claimed and handled under CSA policy.'],
  ['Who can see my report?', 'You and CSA staff. Other students and guests never see your reports, answers, or photos. CSA checks guest reports before anything moves forward.'],
  ['How does matching work?', 'LyFind uses real local AI: DINOv2 for photo-to-photo (the same physical item) and CLIP for words versus photos. Models run on this computer. Photos never leave the server. If the photos are not the same item, matching words cannot raise the score. CSA still checks ID before handover.'],
  ['Why did I get a match / why did I not?', 'A Strong match means the photos look like the same item. Possible means the typed details overlap, but the photos did not prove it. Below that, nothing is shown. Staff always decide. A high score is never proof of ownership.'],
  ['How should I take a photo?', 'Photograph your own item, not a similar one from the internet. Fill the frame, use even light, and include a mark only you would know (keychain, scratch, sticker). CSA photographs the found item the same way.']
];
const STATUS_HELP = [
  ['Reported', 'You told CSA what you lost, or someone handed in what they found.'],
  ['Matched', 'CSA thinks a found item could be yours and invites you to claim it.'],
  ['Verified', 'You answered the ownership questions and CSA checked your ID at the office.'],
  ['Released', 'CSA handed the item to you and recorded it. The report is closed.']
];
const STAFF_FAQS = [
  ['How do I handle a guest report?', 'Guest reports are listed under Lost reports and marked Needs a check. Open the report, then press Check report if it looks real. Matching waits until you do. If it looks like spam, press Hide report. The record is kept.'],
  ['How do I receive an item?', 'Only after the item is in the office. Press Receive item, fill in the form, and add a clear photo and the private details. Matching runs right away. If a finder reported it first, open Found items and press Receive item on their report.'],
  ['What happens when I approve a match?', 'The owner is invited to answer ownership questions. Their answers show under Claims. Nothing is handed over yet.'],
  ['How do I release an item?', 'Open the claim under Claims. Check the answers, then check the owner’s valid ID in person. Press Pass office check, then press Hand over item. The return is written to the activity log.'],
  ['A visitor has no account. Can I still file a report?', 'Yes. Press Report for a guest and enter their personal email. If they have no account, they get a one-time code by email and the report saves when they finish signing up. Staff never see the code.'],
  ['Why is a match not shown?', 'Scores under 60 are hidden. If both sides have photos and they are not the same item, the written details cannot lift the pair. A clear photo of the item helps most.'],
  ['Where is the log?', 'Under Administration, then Logs. It cannot be edited.']
];
const DESK_GUIDE = [
  'Open the <b>Dashboard</b>. The four numbers are what is waiting: lost reports, found items, matches, and claims.',
  'On <b>Lost reports</b>, open Action needed. Press Check report on a guest report before it can be matched.',
  'When the item is in the office, press <b>Receive item</b> and add a photo. Items still on the way are under Awaiting arrival.',
  'On <b>Matches</b>, approve a pair to invite the owner, or reject it if it is not the same item. A score is a hint, not proof.',
  'On <b>Claims</b>, read the answers, check a valid ID at the office, then press Hand over item.'
];
const MEMBER_GUIDE = [
  'Press <b>Report lost</b>. Say what it is, where on campus, and when. A photo of your own item helps.',
  'Found something? Press <b>Report found</b>, say where it is now, and bring it to the CSA office if you still have it.',
  'Follow each item on your <b>Dashboard</b>. It moves through Reported, Matched, Verified, and Released.',
  'When CSA invites you, open <b>My claims</b> and answer questions only you would know.',
  'Bring a valid ID to the CSA office. CSA does not hand an item over without one.'
];
const GUEST_GUIDE = [
  'Press <b>Report lost</b> or <b>Report found</b>. Say what it is, where on campus, and when. You can send up to 3 of each a day.',
  'CSA checks each guest lost report before it moves forward.',
  'Follow it on your <b>Dashboard</b>. It moves through Reported, Matched, Verified, and Released.',
  'If you still have a found item, bring it to the CSA office after you report it.',
  'When CSA invites you, open <b>My claims</b>, answer the questions, and bring a valid ID.'
];
const STAFF_MANUAL = [
  ['Dashboard', 'The home page of the desk. The four numbers are lost reports, found items, matches, and claims. Press a number to open that page. Receive item is only for something already in the office. Report for a guest files a lost report for a visitor who has no account yet.'],
  ['Lost reports', 'Action needed means you should do something now, including guest reports that still need a check. In progress means the owner was invited or a claim is open. Closed means the item was handed back or the report was hidden. Hidden reports stay on record.'],
  ['Found items', 'In the office is what you can match and hand over. Awaiting arrival is a found report that has not reached the desk. Press Receive item only when the item is in front of you, and add a photo plus private details only the owner would know.'],
  ['Matches', 'Needs a decision means you still approve or reject the pair. Waiting for the owner means you already approved it. Strong starts at 60. Possible starts at 40. Strong also needs agreeing clues. Lower scores stay hidden. Open Why this match? to see what the score used. Approving invites the owner. It does not hand the item over.'],
  ['Claims', 'Pending means the owner answered and you still need to check them. Read the answers, then check a valid ID at the office, pass the office check, and press Hand over item. Completed lists items already handed back or not approved. Claims closest to pickup are listed first.'],
  ['Notifications', 'Each card is something waiting: a guest report to check, a match to review, or a claim to open. The button on the card takes you to that item.'],
  ['Administration', 'Staff is who can use this desk. Allowed emails limits school sign-in when the list is in use. People is where you set a password after a valid ID, or block an account. Logs is the record of sign-ins, checks, and handovers, and it cannot be edited. Clean up marks old unclaimed items as not claimed.'],
  ['Account', 'Your name and role. Appearance, under Account, switches Light and Dark. Set new password asks for the password you use now. LyFind cannot email a new password. If you forget it while you are signed in, open Staff and press Edit next to your name.']
];
const MEMBER_MANUAL = [
  ['Sign in', 'Students and professors use an @lpunetwork.edu.ph email. The first time, you get one code, then you choose a password. After that, every login is email and password. Guests use a personal email and an email code, without a password.'],
  ['Report lost', 'Say what it is, where on campus, and when. Add a color, a brand if you know it, and a photo of your own item. Do not use a picture of a similar item from the internet.'],
  ['Report found', 'Say what you found, where, and where it is now: with you, with campus security, or left where it was. If you still have it, bring it to the CSA office. Nobody can claim it until it arrives.'],
  ['Dashboard', 'Your home page. It shows open reports, invitations, claims in progress, and items already handed back. Each item moves through Reported, Matched, Verified, and Released.'],
  ['My reports', 'Lost lists what you reported missing. Found lists what you turned in or are still bringing to the office. Open and Done split the list once you have a few.'],
  ['My claims', 'When CSA thinks an office item may be yours, the invitation is here. Answer questions only you would know, then bring a valid ID. CSA does not show you match scores.'],
  ['Notifications', 'Messages from CSA about your report or claim, newest first. Older ones are grouped by week, month, or year.'],
  ['Account and password', 'Your name, email, and phone if you added one. Appearance switches Light and Dark. Set new password asks for the password you use now. If you forget it, visit the CSA office with a valid ID. Staff will set a new password. LyFind cannot email one.']
];
const PUBLIC_MANUAL = [
  ['Who can use it', 'Students and professors sign up with an @lpunetwork.edu.ph email. Guests sign up with a personal email. LPU accounts choose a password after email verification. Guests sign in with an email code. The testing workspace shows demonstration codes when email is disconnected.'],
  ['Report something lost', 'After you sign in, press Report lost. Name the item, the place on campus, and the date. A photo of your own item helps CSA compare it with what is at the office.'],
  ['Report something found', 'Press Report found and say where the item is now. If you still have it, bring it to the CSA office. It cannot be claimed until it is there.'],
  ['The four steps', 'Reported means CSA has your report or the item. Matched means CSA invites you to claim a possible item. Verified means your answers and your ID checked out. Released means the item was handed to you.'],
  ['Pick-up', 'Bring a valid ID. CSA never hands an item over without one. You do not see match scores. Staff decide, then check you in person.']
];
const DEMO_ACCOUNTS = [['Student 1', 'demo.student@example.test'], ['Student 2','demo.student2@example.test'], ['Professor', 'demo.professor@example.test'], ['Guest', 'demo.guest@example.test'], ['CSA staff', 'demo.admin@example.test']];
function quickTesting() {
  if (!state.config.demo_mode) return openTestingWorkspace();
  const roles = ['student', 'student2', 'professor', 'guest', 'admin'];
  const icons = ['user', 'user', 'documents', 'mail', 'shield'];
  openModal(`<div class="modal-head"><div><p class="form-kicker">Testing workspace</p><h2 id="modal-title">Try an account</h2><p>Fictional accounts, separate from real records. Pick one to continue.</p></div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div><div class="modal-body quick-accounts">${DEMO_ACCOUNTS.map(([label, email], index) => `<button type="button" class="quick-account" data-action="test-account" data-id="${roles[index]}"><span class="quick-account-icon">${svg(icons[index])}</span><span><strong>${esc(label)}</strong><small>${esc(email)}</small></span>${svg('arrow')}</button>`).join('')}<p class="meta">Switch accounts here anytime. Changes stay in the testing workspace.</p></div>`);
}
async function openTestingWorkspace() {
  if (!state.config.testing_available) return;
  // Open during the click, before the server starts, so browsers do not block the new tab.
  const tab = window.open('about:blank', '_blank');
  if (tab) tab.opener = null;
  try {
    const result = await api('/api/testing/open', {});
    const url = new URL(result.url);
    if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1') throw new Error('The local testing address could not be opened.');
    url.hash = 'testing&theme=' + readTheme();
    if (tab) tab.location.replace(url.href);
    else location.assign(url.href);
  } catch (error) {
    if (tab) tab.close();
    throw error;
  }
}
const DEMO_PASSWORD = 'DemoOnly!2026';
const PW_MIN = 8;
const PW_MAX = 128;
const PW_RULES = [
  ['length', () => `${PW_MIN} to ${PW_MAX} characters, spaces not counted`, () => `Use ${PW_MIN} to ${PW_MAX} characters. Spaces do not count.`],
  ['identity', () => 'Not your name or email', () => 'Do not use your name or email in your password.'],
  ['letter', () => 'Uppercase and lowercase letters', () => 'Include an uppercase and a lowercase letter.'],
  ['mix', () => 'A number and a symbol', () => 'Include a number and a symbol.']
];
function roleGuide(prefix) {
  const tabsHtml = ROLE_GUIDE.map(([key, label], index) => `<button class="tab" type="button" role="tab" id="${prefix}-tab-${key}" data-guide-tab aria-controls="${prefix}-panel-${key}" aria-selected="${index === 0}" tabindex="${index === 0 ? 0 : -1}">${label}</button>`).join('');
  const panels = ROLE_GUIDE.map(([key, label, steps], index) => `<div class="guide-panel" role="tabpanel" id="${prefix}-panel-${key}" aria-labelledby="${prefix}-tab-${key}" ${index ? 'hidden' : ''}><ol class="guide-steps">${steps.map(step => `<li><span>${step}</span></li>`).join('')}</ol></div>`).join('');
  return `<div class="guide" data-guide><div class="tabs" role="tablist" aria-label="Who are you?">${tabsHtml}</div>${panels}</div>`;
}
function passwordSize(password) {
  return [...String(password || '')].filter(ch => !/\s/u.test(ch)).length;
}
function pwChecks(password, name, email, min) {
  const clean = text => String(text || '').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  const flat = clean(password);
  const local = clean(String(email || '').split('@')[0]);
  const words = String(name || '').split(/\s+/).map(clean);
  const uses = (local.length >= 3 && flat.includes(local)) || words.some(word => word.length >= 3 && flat.includes(word));
  const size = passwordSize(password);
  return { length: size >= min && size <= PW_MAX && [...String(password || '')].length <= PW_MAX, identity: !uses, letter: /\p{Lu}/u.test(password)&&/\p{Ll}/u.test(password), mix: /\p{N}/u.test(password)&&/[^\p{L}\p{N}\s]/u.test(password) };
}
function pwProblem(password, name, email, min) {
  const result = pwChecks(password, name, email, min);
  const rule = PW_RULES.find(([key]) => !result[key]);
  return rule ? rule[2](min) : '';
}
function pwError(name) {
  return `<small class="field-error" id="err-${name}" data-error-for="${name}" hidden></small>`;
}
function passwordInput(name, label, autocomplete, placeholder, extra, optional) {
  return `<label class="field"><span>${label}</span><span class="pw"><input name="${name}" type="password" ${optional ? '' : 'required'} autocomplete="${autocomplete}" placeholder="${esc(placeholder)}" ${extra || ''}><button class="pw-toggle" type="button" data-action="toggle-pw" aria-pressed="false" aria-label="Show ${label.toLowerCase()}" title="Show ${label.toLowerCase()}"><span class="pw-eye">${svg('eye')}</span></button></span>${pwError(name)}</label>`;
}
function passwordPolicy() {
  const length = 'A password needs 8 to 128 characters. Spaces do not count.';
  openModal(`<div class="modal-head"><div><h2 id="modal-title">Password policy</h2><p>These are the rules LyFind already uses when you create or change a password.</p></div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div><div class="modal-body"><ol class="policy-list"><li><b>Length.</b> ${length}</li><li><b>A letter, and a number or a symbol.</b> The password needs at least one letter, plus a number or a symbol.</li><li><b>Not your name or email.</b> Do not use your name, or the part of your email before the @.</li><li><b>A useful shape.</b> A few words with a number works well, like Blue-Tree-Rain-42.</li><li><b>Too many sign-in tries.</b> Five wrong passwords lock that email for 15 minutes.</li><li><b>Forgot your password.</b> Visit the CSA office with a valid ID. Staff will set a new password. LyFind cannot email one.</li></ol><div class="modal-actions"><button class="btn primary" type="button" data-action="close-modal">Close</button></div></div>`);
}
function passwordSet(min, confirm, optional) {
  const rules = PW_RULES.map(([key, label]) => `<li data-rule="${key}"><span class="rule-icon" aria-hidden="true">${svg('cross')}</span><span data-rule-label>${label(min)}</span><span class="sr-only" data-rule-state> (not met yet)</span></li>`).join('');
  return `<div class="pw-set" data-pw-set data-min="${min}">
    ${passwordInput('password', optional ? 'New password' : 'Password', 'new-password', `${PW_MIN} to ${PW_MAX} characters`, 'aria-describedby="pw-hint pw-rules"', optional)}
    <p class="pw-hint" id="pw-hint">Use ${PW_MIN} to ${PW_MAX} characters. Spaces do not count. A few words with a number works well, like Blue-Tree-Rain-42.</p>
    <div class="pw-policy-row"><button class="link-button" type="button" data-action="password-policy">Password policy</button></div>
    <div class="pw-meter"><span class="pw-bar" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="pw-label" data-strength aria-live="polite">Strength: start typing</span></div>
    <ul class="pw-checklist" id="pw-rules" aria-label="Password rules">${rules}</ul>
    ${confirm ? `${passwordInput('confirm', 'Confirm password', 'new-password', 'Type it again', '', optional)}<p class="pw-match" data-match aria-live="polite"></p>` : ''}
  </div>`;
}
function updatePasswordHelper(box) {
  const form = box.closest('form');
  const min = Number(box.dataset.min) || PW_MIN;
  const password = box.querySelector('[name=password]').value;
  const result = pwChecks(password, form.querySelector('[name=name]')?.value, form.querySelector('[name=email]')?.value, min);
  let passed = 0;
  box.querySelectorAll('[data-rule]').forEach(item => {
    const ok = Boolean(password) && result[item.dataset.rule];
    if (ok) passed += 1;
    item.classList.toggle('ok', ok);
    item.querySelector('.rule-icon').innerHTML = svg(ok ? 'check' : 'cross');
    item.querySelector('[data-rule-state]').textContent = ok ? ' (met)' : ' (not met yet)';
    if (item.dataset.rule === 'length') {
      const counted = passwordSize(password);
      item.querySelector('[data-rule-label]').textContent = password
        ? `${counted} counted · ${PW_MIN} to ${PW_MAX}, spaces not counted`
        : `${PW_MIN} to ${PW_MAX} characters, spaces not counted`;
    }
  });
  const size = passwordSize(password);
  const level = !password ? 0 : passed < 4 ? 1 : size >= 18 ? 4 : size >= 14 ? 3 : 2;
  const names = ['start typing', 'too weak', 'okay', 'good', 'strong'];
  box.querySelector('.pw-bar').className = `pw-bar l${level}`;
  box.querySelector('[data-strength]').textContent = `Strength: ${names[level]}`;
  const confirm = box.querySelector('[name=confirm]');
  const match = box.querySelector('[data-match]');
  if (confirm && match) {
    const typed = Boolean(confirm.value);
    const same = typed && confirm.value === password;
    match.hidden = !typed;
    match.className = `pw-match ${same ? 'ok' : 'no'}`;
    match.innerHTML = typed ? `${svg(same ? 'check' : 'cross')}<span>${same ? 'The passwords match.' : 'The passwords are not the same yet.'}</span>` : '';
  }
}
let accessibleFieldId = 0;
function prepareFormAccessibility(root) {
  root.querySelectorAll('.field input:not([type=hidden]):not([type=checkbox]):not([type=radio]), .field select, .field textarea').forEach(input => {
    if (input.dataset.accessibleField) return;
    const label = input.closest('.field');
    const id = `lyfind-field-${++accessibleFieldId}`;
    input.id = input.id || id;
    const caption = label.querySelector(':scope > span:not(.pw)');
    if (caption) {
      caption.id = `${id}-label`;
      input.setAttribute('aria-labelledby', caption.id);
    }
    let error = label.querySelector('[data-error-for]');
    if (!error && input.name) {
      error = document.createElement('small');
      error.className = 'field-error';
      error.dataset.errorFor = input.name;
      error.hidden = true;
      label.append(error);
    }
    const previousError = error?.id;
    if (error) error.id = `${id}-error`;
    const described = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(token => token && token !== previousError);
    label.querySelectorAll(':scope > small:not([data-error-for])').forEach((hint, index) => {
      hint.id = hint.id || `${id}-hint-${index}`;
      described.push(hint.id);
    });
    input.dataset.baseDescription = [...new Set(described)].join(' ');
    restoreFieldDescription(input);
    input.dataset.accessibleField = 'true';
  });
}
function restoreFieldDescription(input) {
  const description = input.dataset.baseDescription;
  if (description === undefined) return;
  if (description) input.setAttribute('aria-describedby', description);
  else input.removeAttribute('aria-describedby');
}
function clearFieldErrors(root) {
  root.querySelectorAll('[data-error-for]').forEach(item => { item.hidden = true; item.textContent = ''; });
  root.querySelectorAll('[aria-invalid]').forEach(input => { input.removeAttribute('aria-invalid'); restoreFieldDescription(input); });
}
function showFieldErrors(root, fields, focusFirst = true) {
  prepareFormAccessibility(root);
  let first = null;
  Object.entries(fields || {}).forEach(([name, message]) => {
    const slot = root.querySelector(`[data-error-for="${name}"]`);
    const input = root.querySelector(`[name="${name}"]`);
    if (!slot || !input) return;
    slot.hidden = false;
    slot.textContent = message;
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', [input.dataset.baseDescription, slot.id].filter(Boolean).join(' '));
    first = first || input;
  });
  if (focusFirst) first?.focus();
  return Boolean(first);
}
document.addEventListener('invalid', event => {
  const input = event.target;
  if (input.form && input.name && input.closest('.field')) {
    showFieldErrors(input.form, { [input.name]: input.validationMessage }, false);
  }
}, true);
function splitPendingName(value) {
  const suffixes = new Set(['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'v']);
  const parts = String(value || '').replace(/,/g, ' ').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return {};
  let suffix = '';
  if (parts.length > 1 && suffixes.has(parts[parts.length - 1].toLowerCase())) suffix = parts.pop();
  if (parts.length === 1) return { first: parts[0], suffix };
  if (parts.length === 2) return { first: parts[0], last: parts[1], suffix };
  return { first: parts[0], middle: parts.slice(1, -1).join(' '), last: parts.at(-1), suffix };
}
function nameFields(seed) {
  const name = splitPendingName(seed);
  return `<div class="name-grid">
    ${field('first_name', 'First name', 'text', { required: true, maxlength: 40, autocomplete: 'given-name', value: name.first || '', placeholder: 'Maria' })}
    ${field('middle_name', 'Middle name', 'text', { maxlength: 40, autocomplete: 'additional-name', value: name.middle || '', placeholder: 'Santos' })}
    ${field('last_name', 'Last name', 'text', { required: true, maxlength: 40, autocomplete: 'family-name', value: name.last || '', placeholder: 'Reyes' })}
    ${field('suffix', 'Suffix', 'text', { maxlength: 12, autocomplete: 'honorific-suffix', value: name.suffix || '', placeholder: 'Jr., III' })}
  </div>`;
}
function studentNumberFrom(email) {
  const local = String(email || '').trim().toLowerCase().split('@')[0];
  return /^\d{4}-\d-\d{5}$/.test(local) && String(email || '').trim().toLowerCase().endsWith('@lpunetwork.edu.ph') ? local : '';
}
function phoneProblem(value) {
  const phone = String(value || '').trim();
  if (!phone) return '';
  if (!/^\+?[\d\s().-]+$/.test(phone)) return 'Use numbers only in the phone field.';
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 10 || digits.length > 15) return 'Enter a phone number with 10 to 15 digits, like 0917 123 4567.';
  return '';
}
function contactFields(email) {
  const number = studentNumberFrom(email);
  const numberField = number ? field('student_number', 'Student number', 'text', { value: number, readonly: true, hint: 'Taken from your LPU email. You do not need to type it.' }) : '';
  return `${numberField}${field('phone', 'Phone', 'tel', { maxlength: 20, placeholder: '0917 123 4567', autocomplete: 'tel', inputmode: 'tel', hint: 'Saved once, so staff never retype it when you claim an item.' })}`;
}
function checkSchoolPassword(data) {
  const problems = {};
  const first = String(data.first_name || '').trim();
  const middle = String(data.middle_name || '').trim();
  const last = String(data.last_name || '').trim();
  const suffix = String(data.suffix || '').trim();
  if (first.length < 2) problems.first_name = 'Enter at least two letters.';
  else if (first.length > 40) problems.first_name = 'Use 40 characters or fewer.';
  if (last.length < 2) problems.last_name = 'Enter at least two letters.';
  else if (last.length > 40) problems.last_name = 'Use 40 characters or fewer.';
  if (middle.length > 40) problems.middle_name = 'Use 40 characters or fewer.';
  if (suffix.length > 12) problems.suffix = 'Use 12 characters or fewer.';
  const display = [first, middle, last, suffix].filter(Boolean).join(' ');
  const weak = pwProblem(data.password || '', display, data.email, PW_MIN);
  if (weak) problems.password = weak;
  if ((data.confirm || '') !== (data.password || '')) problems.confirm = 'The two passwords are not the same.';
  const phone = phoneProblem(data.phone);
  if (phone) problems.phone = phone;
  return problems;
}
function checkSignUp(data) {
  const problems = {};
  if (!String(data.name || '').trim()) problems.name = 'Add your name.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(data.email || '').trim())) problems.email = 'Enter a valid email address, like you@example.com.';
  const weak = pwProblem(data.password || '', data.name, data.email, PW_MIN);
  if (weak) problems.password = weak;
  if ((data.confirm || '') !== (data.password || '')) problems.confirm = 'The two passwords are not the same.';
  return problems;
}
function helpContent() {
  const staff = admin();
  const signedIn = Boolean(state.user);
  const guest = state.user?.role === 'guest';
  const testing= !signedIn && state.config.testing_available ? '<p><button class="link-button" type="button" data-action="open-testing">Testing workspace</button></p>' : '';
  const demo = !signedIn && state.config.demo_mode ? `<section class="card quiet" aria-labelledby="demo-h"><details class="fold"><summary id="demo-h">Sample accounts</summary><p class="muted">Made-up people for trying LyFind. The samples already have a password. Use the email and password form on the sign-in page.</p><div class="table-wrap"><table><thead><tr><th>Role</th><th>Email</th></tr></thead><tbody>${DEMO_ACCOUNTS.map(([role, email]) => `<tr><td>${role}</td><td>${esc(email)}</td></tr>`).join('')}</tbody></table></div><p class="meta" style="margin:16px 0 0">Password for the sample accounts: <b>${DEMO_PASSWORD}</b></p></details></section>` : '';
  const stages = `<ol class="tracker help-tracker" aria-label="The four steps">${STAGES.map((name, index) => `<li class="later"><span class="step-name"><span class="mark">${index + 1}</span><span>${name}</span></span><p>${STATUS_HELP[index][1]}</p></li>`).join('')}</ol>`;
  const pages = !signedIn ? PUBLIC_MANUAL : staff ? STAFF_MANUAL : MEMBER_MANUAL;
  const manual = `<section class="card" aria-labelledby="help-manual"><h2 id="help-manual">How to use LyFind</h2><p class="card-sub">${staff ? 'What each page on the staff desk is for, in the order you use them.' : 'What to do on each page, from sign-in to pick-up.'}</p><div class="manual">${pages.map(([title, text]) => `<h3>${title}</h3><p>${text}</p>`).join('')}</div></section>`;
  const matching = `<section class="card" aria-labelledby="help-match"><h2 id="help-match">How matching works</h2>
      <p class="card-sub">Matching suggests which office item might belong to a lost report. It runs on this computer with DINOv2 and CLIP. Photos never leave the server.</p>
      <ul class="tick-list">
        <li>${svg('check')}<span><b>Same kind only.</b> A phone is not compared with a bag. Two different black backpacks still must not score as a Strong match.</span></li>
        <li>${svg('check')}<span><b>Photos come first.</b> If both sides sent a photo and those photos are not the same item, the pair is hidden. Matching words cannot raise it.</span></li>
        <li>${svg('check')}<span><b>What the numbers mean.</b> Strong starts at 60. Possible starts at 40. Strong also needs agreeing clues. Lower scores stay hidden. Students, professors, and guests never see scores.</span></li>
        <li>${svg('check')}<span><b>Staff still decide.</b> A score is a hint, not proof. CSA checks the answers and a valid ID before handover.</span></li>
      </ul>
      <p class="muted" style="margin:16px 0 0">Photograph the actual item. A similar bag from the internet will not match the one in the office.</p>
    </section>`;
  const steps = list => `<ol class="guide-steps">${list.map(step => `<li><span>${step}</span></li>`).join('')}</ol>`;
  const start = !signedIn
    ? `<section class="card" aria-labelledby="help-start"><h2 id="help-start">Get started</h2><p class="card-sub">Students and professors share one path. Guests have their own.</p>${roleGuide('help')}</section>`
    : `<section class="card" aria-labelledby="help-start"><h2 id="help-start">${staff ? 'Your daily routine' : 'What to do next'}</h2><p class="card-sub">${staff ? 'Work from the Dashboard, top to bottom.' : 'Five steps from a lost item to pick-up.'}</p>${steps(staff ? DESK_GUIDE : guest ? GUEST_GUIDE : MEMBER_GUIDE)}</section>`;
  const faqs = staff ? [...STAFF_FAQS, FAQS[4], FAQS[8]] : FAQS;
  const office = staff ? '' : `<section class="card" aria-labelledby="help-office"><div class="card-head"><h2 id="help-office">Contact the CSA office</h2></div><p class="card-sub">CSA handles lost and found at LPU Cavite. Bring a valid ID when you pick up an item. Numbers and email below are from the university’s public contact pages.</p>${officeInfo()}<p style="margin:16px 0 0"><a class="btn secondary" href="mailto:${esc(OFFICE.email)}">${svg('mail')}<span>Email CSA</span></a></p></section>`;
  const blurb = !signedIn ? 'A short manual: how to sign in, report an item, and pick it up.' : staff ? 'A manual for the staff desk: what each page is for, and what to press.' : 'A manual for your account: how to report an item, follow it, and pick it up.';
  const jump = [['#help-manual', 'How to use'], ['#help-start', signedIn ? (staff ? 'Daily routine' : 'What to do next') : 'Get started'], ['#help-match', 'Matching'], ['#help-status', 'Statuses'], ['#help-faq', 'Questions']];
  if (!staff) jump.push(['#help-office', 'CSA office']);
  const contents = `<nav class="help-jump" aria-label="On this page">${jump.map(([href, label]) => `<a href="${href}">${label}</a>`).join('')}</nav>`;
  return `<div class="page-stack help-page">${pageHead('Help', blurb)}
    ${contents}
    <div class="help-rail">
    ${manual}
    ${start}
    ${matching}
    <section class="card" aria-labelledby="help-status"><h2 id="help-status">What the statuses mean</h2><p class="card-sub">Every item moves through these four steps.</p>${stages}</section>
    <section class="card" aria-labelledby="help-faq"><h2 id="help-faq">Common questions</h2><label class="search-box help-search">Search the questions<input type="search" id="help-search" placeholder="Try “photo”, “ID”, or “match”" autocomplete="off" aria-controls="help-faq-list"></label><p class="meta help-count" id="help-count" role="status" aria-live="polite"></p><div class="faq flush" id="help-faq-list">${faqs.map(([question, answer]) => `<details class="faq-item"><summary>${question}</summary><p>${answer}</p></details>`).join('')}</div></section>
    ${office}${demo}${testing}
    ${state.config.demo_mode?`<section class="card"><details class="fold"><summary>Try LyFind with a classmate</summary><p>Use the testing accounts. Ask someone unfamiliar with LyFind to try without coaching.</p><ol><li>Start a lost report, close it, and resume the draft.</li><li>Review the details, correct one, and submit.</li><li>Read Your next step and explain what happens next.</li><li>Switch to Professor, report something found, and explain when it becomes claimable.</li><li>Try larger text and use the keyboard to open and close Accessibility.</li></ol><p>Record where they pause, whether they finish unaided, and one thing they would change. Ask: “What did you expect?” Use docs/CLASSMATE_USABILITY_TEST.md for the group worksheet.</p><p class="meta">Prepared exercise. Real classmate sessions still need to be carried out by your group.</p></details></section>`:''}
    </div></div>`;
}
function filterHelp(text) {
  const needle = text.trim().toLowerCase();
  let shown = 0;
  document.querySelectorAll('#help-faq-list .faq-item').forEach(item => {
    const match = !needle || item.textContent.toLowerCase().includes(needle);
    item.hidden = !match;
    item.open = Boolean(needle) && match;
    if (match) shown += 1;
  });
  const note = document.querySelector('#help-count');
  if (note) note.textContent = !needle ? '' : shown ? `${shown} answer${shown === 1 ? '' : 's'} found.` : 'No answers found. Try another word, or contact the CSA office below.';
}
function renderPublicHelp() {
  app.innerHTML = `${publicNav(false)}<main id="main" tabindex="-1"><div class="wrap help-public">${helpContent()}<div class="help-cta"><button class="btn primary big" type="button" data-action="go-register">Sign up</button><button class="btn secondary big" type="button" data-action="go-login">Login</button></div></div></main>`;
  closeMenu(false);
  finishRender();
}
function publicNav(onWelcome) {
  const pageLinks = [['what', 'About', 'home'], ['how', 'Steps', 'activity'], ['highlights', 'Highlights', 'spark'], ['contact', 'Contact', 'pin']];
  const onAuth = !state.user && state.screen === 'auth';
  const onHelp = !state.user && state.screen === 'help';
  const onLogin = onAuth && ['signin', 'reset-request', 'reset-password'].includes(state.authMode);
  const onSignup = onAuth && !onLogin;
  const topLink = ([id, label]) => onWelcome ? `<a href="#${id}">${label}</a>` : `<button class="pub-link" type="button" data-action="go-section" data-section="${id}">${label}</button>`;
  const sideLink = ([id, label, icon]) => onWelcome
    ? `<a class="nav-item" href="#${id}"><span aria-hidden="true">${svg(icon)}</span><span>${label}</span></a>`
    : `<button class="nav-item" type="button" data-action="go-section" data-section="${id}"><span aria-hidden="true">${svg(icon)}</span><span>${label}</span></button>`;
  const desktop = `<nav class="pub-links" aria-label="${onWelcome ? 'On this page' : 'Site'}">${pageLinks.map(topLink).join('')}<button class="pub-link" type="button" data-action="go-help"${onHelp ? ' aria-current="page"' : ''}>Help</button></nav>`;
  const drawerItems = pageLinks.map(sideLink).join('')
    + `<button class="nav-item" type="button" data-action="go-help"${onHelp ? ' aria-current="page"' : ''}><span aria-hidden="true">${svg('help')}</span><span>Help</span></button>`;
  return `<header class="pub-nav"><div class="pub-nav-inner"><button class="menu-button" type="button" data-action="menu" aria-label="Open menu" aria-controls="sidebar" aria-expanded="false">${svg('menu')}</button><button class="wordmark wh1128-wordmark" type="button" data-action="go-welcome" aria-label="LyFind home"><span class="logo-mark">${LOGO}</span><span>LYFIND</span></button>${desktop}<div class="pub-actions"><button class="pub-link" type="button" data-action="go-login"${onLogin ? ' aria-current="page"' : ''}>Login</button><button class="pub-link" type="button" data-action="go-register"${onSignup ? ' aria-current="page"' : ''}>Sign up</button></div></div></header><button class="nav-overlay" type="button" data-action="menu-close" aria-label="Close menu" hidden></button><aside class="pub-drawer" id="sidebar"><div class="drawer-head"><button class="wordmark wh1128-wordmark" type="button" data-action="go-welcome" aria-label="LyFind home"><span class="logo-mark">${LOGO}</span><span>LYFIND</span></button><button class="icon-button drawer-close" type="button" data-action="menu-close" aria-label="Close menu">${svg('close')}</button></div><nav class="nav-list" aria-label="Menu">${drawerItems}</nav><div class="drawer-actions"><button class="btn secondary" type="button" data-action="go-login">Login</button><button class="btn primary" type="button" data-action="go-register">Sign up</button></div></aside>`;
}
function renderWelcome() {
  const programs = [
    ['/assets/wix-items.jpg?v=244', 'Everyday belongings logged at LPU Cavite', '01 · Report Lost or Found', 'Under 2 minutes', 'Open to LPU and Guests', 'Start Report', 'go-login'],
    ['/assets/wix-desk.jpg?v=244', 'Local AI photo and detail matching desk', '02 · AI Photo & Detail Match', 'DINOv2 and CLIP', 'Private on server', 'Learn More', 'go-help'],
    ['/assets/wix-hero.jpg?v=244', 'Found items secured at the CSA office', '03 · Verified Office Handover', 'Two-step check', 'Valid ID required', 'Sign In', 'go-login']
  ];
  const facts = [
    ['4 steps', 'Report to pick-up'],
    ['ID required', 'At every handover'],
    ['LPU email', 'Code once, then password'],
    ['On record', 'Every return is logged']
  ];
  const heroSlides = [
    ['/assets/campus.jpg?v=244', 'Lyceum of the Philippines University Cavite campus', '01 / LPU Cavite Campus'],
    ['/assets/wix-hero.jpg?v=244', 'Campus bench belongings ready for safe return', '02 / Campus Belongings'],
    ['/assets/wix-desk.jpg?v=244', 'CSA office review and matching desk', '03 / AI-Assisted Matching'],
    ['/assets/wix-bag.jpg?v=244', 'Burgundy campus backpack in afternoon sunlight', '04 / Verified Handover']
  ];
  const aboutSlides = [
    ['/assets/wix-bag.jpg?v=244', 'Burgundy canvas campus backpack in warm afternoon sunlight', 'Everyday Campus Items'],
    ['/assets/wix-items.jpg?v=244', 'Everyday belongings logged at LPU Cavite', 'Logged With Care'],
    ['/assets/wix-desk.jpg?v=244', 'CSA office desk for photo and detail matching', 'Private Office Review'],
    ['/assets/campus.jpg?v=244', 'Lyceum of the Philippines University Cavite campus', 'LPU Cavite CSA']
  ];
  const squares = [
    ['/assets/campus.jpg?v=244', 'Lyceum of the Philippines University Cavite campus', '01 / LPU Cavite', 'Private Office Inventory'],
    ['/assets/wix-desk.jpg?v=244', 'Matching lost reports with office items', '02 / Gemini AI', 'AI Visual & Text Matching'],
    ['/assets/wix-hero.jpg?v=244', 'Verified handover at CSA office', '03 / CSA Office', 'Two-Step Owner Verification']
  ];
  const voices = [
    ['Report a lost or found item in under two minutes with your @lpunetwork.edu.ph email and follow all four recovery steps from one clear page.', 'Students & Professors · LPU Cavite Community'],
    ['Lost something while visiting campus? Verify a one-time code with your personal email, file your report, and track every CSA update.', 'Campus Guests · Visitors & Parents'],
    ['Every found item is tagged, compared locally with AI assistance, verified in person with valid ID, and written to the official log.', 'CSA Desk Staff · Gate 1, Admin Building']
  ];
  app.innerHTML = `${publicNav(true)}<main id="main" class="wh1128-landing">
    <section class="wh1128-hero"><div class="wh1128-wrap">
      <div class="wh1128-hero-top">
        <h1 class="wh1128-h1">Report. Match. <br>Recover.</h1>
        <div class="wh1128-hero-side">
          <p class="wh1128-hero-lead">Report lost or found belongings across LPU Cavite. CSA keeps every found item safe at the office until it is verified and returned.</p>
          <div class="wh1128-hero-cta">
            <button class="btn wh1128-pill" type="button" data-action="go-login">Sign In</button>
            <button class="btn primary" type="button" data-action="go-register">Create Account</button>
          </div>
          <p class="hero-note">Students and professors use an ${STUDENT_EXAMPLE} email. Guests use a personal email and a sign-in code.</p>
        </div>
      </div>
      <div class="wh1128-hero-photo wh1128-slideshow" data-hero-slideshow>
        ${heroSlides.map(([src, alt, cap], i) => `<figure class="hero-slide${i === 0 ? ' is-active' : ''}" data-slide="${i}"><img src="${src}" alt="${esc(alt)}"${i > 0 ? ' loading="lazy"' : ''}><figcaption class="hero-slide-cap">${esc(cap)}</figcaption></figure>`).join('')}
        <div class="hero-slide-dots" role="tablist" aria-label="Campus photos">
          ${heroSlides.map(([, , cap], i) => `<button type="button" class="hero-dot${i === 0 ? ' is-active' : ''}" data-action="hero-slide" data-slide="${i}" aria-label="${esc(cap)}" aria-selected="${i === 0}"></button>`).join('')}
        </div>
      </div>
    </div></section>
    <hr class="wh1128-rule">
    <section class="wh1128-about" id="what"><div class="wh1128-wrap">
      <div class="wh1128-about-grid">
        <div class="wh1128-about-left">
          <h2 class="wh1128-h2">About</h2>
          <div class="wh1128-about-bottom">
            <p>Items found around LPU Cavite are kept safely at the Center for Student Affairs. LyFind connects your lost report directly to office inventory, using local photo and detail matching so you never have to walk from desk to desk guessing if anyone turned it in.</p>
            <button class="btn wh1128-pill" type="button" data-action="go-section" data-section="how">How It Works</button>
          </div>
        </div>
        <div class="wh1128-about-photo wh1128-about-slideshow" data-about-slideshow>
          ${aboutSlides.map(([src, alt, cap], i) => `<figure class="about-slide${i === 0 ? ' is-active' : ''}" data-about-slide="${i}"><img src="${src}" alt="${esc(alt)}" loading="lazy"><figcaption class="hero-slide-cap">${esc(cap)}</figcaption></figure>`).join('')}
        </div>
      </div>
    </div></section>
    <hr class="wh1128-rule">
    <section class="wh1128-programs" id="how"><div class="wh1128-wrap">
      <div class="wh1128-programs-head">
        <h2 class="wh1128-h2">How Campus <br>Recovery Works</h2>
        <p>A clear four-step workflow connects your campus report to a verified handover. CSA compares photos and clues privately on campus and requires a valid ID before release.</p>
      </div>
      <div class="wh1128-program-grid">
        ${programs.map(([src, alt, title, line1, line2, cta, action]) => `<article class="wh1128-program-card"><img class="wh1128-program-img" src="${src}" alt="${esc(alt)}" loading="lazy"><h3 class="wh1128-program-title">${esc(title)}</h3><div class="wh1128-program-meta"><span>${esc(line1)}</span><span>${esc(line2)}</span></div><button class="btn wh1128-pill" type="button" data-action="${esc(action)}">${esc(cta)}</button></article>`).join('')}
      </div>
    </div></section>
    <section class="wh1128-facts-band" aria-labelledby="standards-h"><div class="wh1128-wrap">
      <h2 class="wh1128-h2" id="standards-h">Campus Recovery Standards</h2>
      <div class="stats-strip wh1128-facts-grid" aria-label="How LyFind works">
        ${facts.map(([n, label]) => `<div><strong>${n}</strong><span>${label}</span></div>`).join('')}
      </div>
    </div></section>
    <section class="wh1128-dark-band" id="highlights">
      <div class="wh1128-dark-top"><div class="wh1128-wrap">
        <h2 class="wh1128-h2">Inside the CSA System</h2>
        <div class="wh1128-square-grid">
          ${squares.map(([src, alt, tag, title]) => `<article class="wh1128-square-card"><img src="${src}" alt="${esc(alt)}" loading="lazy"><div class="square-photo-scrim" aria-hidden="true"></div><span class="wh1128-square-tag">${esc(tag)}</span><h3 class="wh1128-square-title">${esc(title)}</h3></article>`).join('')}
        </div>
      </div></div>
      <hr class="wh1128-rule wh1128-rule-dark">
      <div class="wh1128-dark-bottom"><div class="wh1128-wrap">
        <h2 class="wh1128-h2">Built for the Campus Community</h2>
        <div class="wh1128-zigzag">
          ${voices.map(([quote, by]) => `<article class="wh1128-zigzag-card"><p class="wh1128-zigzag-quote">“${esc(quote)}”</p><span class="wh1128-zigzag-by">${esc(by)}</span></article>`).join('')}
        </div>
      </div></div>
    </section>
  </main><footer class="wh1128-footer" id="contact"><div class="wh1128-wrap">
    <div class="wh1128-footer-grid">
      <div>
        <h2 class="wh1128-footer-h">Ready to Report or <br>Claim an Item?</h2>
        <form class="wh1128-footer-form" data-form="footer-start" novalidate>
          ${field('email', 'Your LPU or Personal Email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your ' + STUDENT_EXAMPLE + ' or personal email' })}
          <div class="wh1128-footer-actions">
            <button class="btn wh1128-pill" type="submit">Sign In</button>
            <button class="btn primary" type="button" data-action="go-register">Create Account</button>
          </div>
        </form>
        <div class="footer-editorial-links">
          <a href="#what">About</a>
          <a href="#how">How It Works</a>
          <a href="#highlights">Highlights</a>
          <button class="footer-link" type="button" data-action="go-help">Help</button>
          <button class="footer-link" type="button" data-action="go-register">Sign Up</button>
        </div>
      </div>
      <div class="wh1128-footer-right">
        <span class="wordmark small wh1128-wordmark"><span class="logo-mark">${LOGO}</span><span>LYFIND</span></span>
        <div class="footer-editorial-contact">
          <a href="tel:${esc(OFFICE.phone.replace(/[^\d+]/g, ''))}">${esc(OFFICE.phone)}</a>
          <a href="mailto:${esc(OFFICE.email)}">${esc(OFFICE.email)}</a>
        </div>
        <div class="footer-editorial-contact">
          <span>${esc(OFFICE.name)}</span>
          <span>LPU Cavite, Governor’s Drive, General Trias</span>
          <span>${esc(OFFICE.hours)}</span>
        </div>
        <p class="wh1128-footer-meta">© 2026 LyFind · LPU Cavite CSA</p>
      </div>
    </div>
  </footer>`;
  closeMenu(false);
  finishRender();
  watchSections();
  startHeroSlideshow();
}
let heroSlideTimer = null;
let aboutSlideTimer = null;
function setHeroSlide(index) {
  const wrap = document.querySelector('[data-hero-slideshow]');
  if (!wrap) return;
  const slides = [...wrap.querySelectorAll('.hero-slide')];
  const dots = [...wrap.querySelectorAll('.hero-dot')];
  if (!slides.length) return;
  const next = ((index % slides.length) + slides.length) % slides.length;
  slides.forEach((el, i) => el.classList.toggle('is-active', i === next));
  dots.forEach((el, i) => {
    el.classList.toggle('is-active', i === next);
    el.setAttribute('aria-selected', String(i === next));
  });
  wrap.dataset.index = String(next);
}
function setAboutSlide(index) {
  const wrap = document.querySelector('[data-about-slideshow]');
  if (!wrap) return;
  const slides = [...wrap.querySelectorAll('.about-slide')];
  if (!slides.length) return;
  const next = ((index % slides.length) + slides.length) % slides.length;
  slides.forEach((el, i) => el.classList.toggle('is-active', i === next));
  wrap.dataset.index = String(next);
}
function startHeroSlideshow() {
  if (heroSlideTimer) { clearInterval(heroSlideTimer); heroSlideTimer = null; }
  if (aboutSlideTimer) { clearInterval(aboutSlideTimer); aboutSlideTimer = null; }
  const wrap = document.querySelector('[data-hero-slideshow]');
  const aboutWrap = document.querySelector('[data-about-slideshow]');
  if (wrap) wrap.dataset.index = '0';
  if (aboutWrap) aboutWrap.dataset.index = '0';
  if (document.documentElement.dataset.reducedMotion === 'true' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (wrap) {
    heroSlideTimer = setInterval(() => {
      const activeWrap = document.querySelector('[data-hero-slideshow]');
      if (!activeWrap) { clearInterval(heroSlideTimer); heroSlideTimer = null; return; }
      setHeroSlide((Number(activeWrap.dataset.index) || 0) + 1);
    }, 5000);
  }
  if (aboutWrap) {
    aboutSlideTimer = setInterval(() => {
      const activeAbout = document.querySelector('[data-about-slideshow]');
      if (!activeAbout) { clearInterval(aboutSlideTimer); aboutSlideTimer = null; return; }
      setAboutSlide((Number(activeAbout.dataset.index) || 0) + 1);
    }, 4500);
  }
}
let sectionSpy = null;
let sectionScrollHandler = null;
function watchSections() {
  sectionSpy?.disconnect();
  if (sectionScrollHandler) {
    window.removeEventListener('scroll', sectionScrollHandler);
    sectionScrollHandler = null;
  }
  const links = [...document.querySelectorAll('.pub-links a[href^="#"]')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const setActive = href => {
    links.forEach(link => {
      if (link.getAttribute('href') === href) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  if (window.scrollY < 160) setActive('#what');
  sectionSpy = new IntersectionObserver(entries => {
    if (window.scrollY < 160) { setActive('#what'); return; }
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      setActive(`#${entry.target.id}`);
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  links.forEach(link => { const target = document.querySelector(link.getAttribute('href')); if (target) sectionSpy.observe(target); });
  sectionScrollHandler = () => {
    if (!document.querySelector('.wh1128-landing')) {
      window.removeEventListener('scroll', sectionScrollHandler);
      sectionScrollHandler = null;
      return;
    }
    if (window.scrollY < 160) setActive('#what');
  };
  window.addEventListener('scroll', sectionScrollHandler, { passive: true });
}
function loginPane(errorBox, microsoft) {
  const resetLink = state.config.school_email_ready ? ' <button class="link-button" type="button" data-action="go-reset">Reset password with an email code</button> or v' : ' V';
  return `<h2>Sign in to LyFind</h2><p class="auth-sub">Students, professors, and CSA staff use their email and password. Guests can request an email code below.</p>${errorBox}
    <form data-form="login" novalidate>${field('email', 'Email', 'email', { required: true, maxlength: 254, autocomplete: 'username', placeholder: 'Enter your email' })}${passwordInput('password', 'Password', 'current-password', 'Enter your password')}<div class="forgot-row"><button class="link-button" type="button" data-action="password-policy">Password policy</button><button class="link-button" type="button" data-action="forgot-password">Forgot password?</button></div><p class="note" role="note" id="forgot-note" hidden>${resetLink.trimStart()}isit the CSA office with a valid ID so staff can set a new password.</p><button class="btn primary full big" type="submit">Login</button></form>
    <p class="auth-switch">Don't have an account? <button class="link-button" type="button" data-action="go-register">Sign up</button></p>${microsoft ? `<div class="auth-extra">${microsoft}</div>` : ''}`;
}
function signupPane(errorBox) {
  const guest = state.signupKind === 'guest';
  const kindTabs = `<div class="kind-tabs" role="tablist" aria-label="Account type">${[['lpu', 'LPU'], ['guest', 'Guest']].map(([key, label]) => {
    const on = (key === 'guest') === guest;
    return `<button class="kind-tab" type="button" role="tab" data-action="signup-kind" data-kind="${key}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${label}</button>`;
  }).join('')}</div>`;
  const panel = guest
    ? `<p class="kind-note">Use a personal email to sign up as a guest.</p><form data-form="register" novalidate>${field('email', 'Personal email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your email' })}<div class="hp" aria-hidden="true"><label>Leave this empty<input name="website" type="text" tabindex="-1" autocomplete="off"></label></div><button class="btn primary full big" type="submit">Send code</button></form>`
    : `<p class="kind-note">For LPU students and professors. Use your ${STUDENT_EXAMPLE} email.</p><form data-form="school-request" novalidate>${field('email', 'LPU email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your ' + STUDENT_EXAMPLE })}<button class="btn primary full big" type="submit">Send code</button></form>`;
  return `<h2>Create your account</h2><p class="auth-sub">We email a code once. LPU accounts choose a password after verification. Guests continue with the code.</p>${errorBox}${kindTabs}${panel}
    <p class="auth-switch">Already have an account? <button class="link-button" type="button" data-action="go-login">Login</button></p>`;
}
function renderAuth() {
  const mode = state.authMode;
  const pending = state.pending;
  const onRegister = mode === 'register' || mode === 'school' || mode === 'school-password' || mode === 'guest-details' || (mode === 'code' && pending?.kind === 'signup');
  const microsoft = state.config.microsoft_enabled ? '<a class="btn secondary full" href="/auth/microsoft">Sign in with Microsoft</a>' : '';
  const errorBox = '<div data-auth-error class="form-error" role="alert" hidden></div>';
  const back = action => `<button class="btn secondary sm back-link" type="button" data-action="${action}">${svg('arrow')}<span>Back</span></button>`;
  let body;
  if(mode==='setup-admin'){
    body=`<h2>Set up CSA access</h2><p>Create the first administrator for this installation.</p>${errorBox}
      <form data-form="setup-admin">${field('name','Full name','text',{required:true,maxlength:120})}
      ${field('email','CSA email','email',{required:true,maxlength:254})}
      ${passwordSet(12,true)}<button class="btn primary full" type="submit">Create administrator</button></form>`;
  } else if (mode === 'school-password' && pending) {
    body = `${back('go-register')}<h2>Choose a password</h2><p class="auth-sub">Your email <b>${esc(pending.email)}</b> is confirmed. This name is what CSA sees, and this password is what you use from now on.</p>${errorBox}
      <form data-form="school-password" novalidate>${nameFields(pending.name)}<input type="hidden" name="email" value="${esc(pending.email)}">${contactFields(pending.email)}${passwordSet(PW_MIN, true)}<button class="btn primary full big" type="submit">Create password and sign in</button></form>`;
  } else if (mode === 'guest-details' && pending) {
    body = `${back('go-register')}<h2>Finish your account</h2><p class="auth-sub">Your email <b>${esc(pending.email)}</b> is confirmed. This name is what CSA sees. The phone is optional. It is saved once, so staff never retype it when you claim an item.</p>${errorBox}
      <form data-form="guest-details" novalidate>${nameFields('')}<input type="hidden" name="email" value="${esc(pending.email)}">${contactFields('')}${passwordSet(PW_MIN, true)}<button class="btn primary full big" type="submit">Create password and sign in</button></form>`;
  } else if (mode === 'reset-request') {
    body = `${back('go-login')}<h2>Reset your password</h2><p class="auth-sub">Enter the email for your student, professor, or guest account. We will send a 6-digit code.</p>${errorBox}
      <form data-form="reset-request" novalidate>${field('email', 'Email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your email' })}<button class="btn primary full big" type="submit">Send reset code</button></form>`;
  } else if (mode === 'reset-password' && pending) {
    body = `${back('go-login')}<h2>Choose a new password</h2><p class="auth-sub">Your email <b>${esc(pending.email)}</b> is confirmed. Choose a new password to sign back in.</p>${errorBox}
      <form data-form="reset-password" novalidate><input type="hidden" name="email" value="${esc(pending.email)}">${passwordSet(PW_MIN, true)}<button class="btn primary full big" type="submit">Save new password</button></form>`;
  } else if (mode === 'code' && pending) {
    const school = pending.kind === 'school';
    const reset = pending.kind === 'reset';
    const formKind = reset ? 'reset-code' : school ? 'school-code' : 'guest-code';
    body = `${back('change-email')}<h2>Check your email</h2>${pending.demo_code?`<div class="note" role="status">Demonstration code <strong>${esc(pending.demo_code)}</strong></div>`:''}<p class="auth-sub">We sent a 6-digit code to <b>${esc(pending.email)}</b>. ${school ? 'Open Outlook (or your school Mail app).' : 'Open the inbox for that address.'} It works once and expires in 10 minutes.</p>${errorBox}
      <form data-form="${formKind}" novalidate>${field('code', '6-digit code', 'text', { required: true, maxlength: 6, autocomplete: 'one-time-code', inputmode: 'numeric', pattern: '[0-9]{6}', placeholder: '123456' })}${!school && !reset?'<label class="check-field" data-remember-guest hidden><input type="checkbox" name="remember_browser" disabled><span>Remember this browser for 30 days. Leave off on shared devices.</span></label>':''}<button class="btn primary full big" type="submit">Continue</button></form>
      <div class="code-actions"><button class="btn secondary sm" type="button" data-action="resend-code" data-resend>Send a new code</button><button class="link-button" type="button" data-action="change-email">Use a different email</button></div>`;
  } else if (mode === 'register' || mode === 'school') {
    const guest = state.signupKind === 'guest';
    const kindTabs = `<div class="kind-tabs" role="tablist" aria-label="Account type">${[['lpu', 'LPU'], ['guest', 'Guest']].map(([key, label]) => {
      const on = (key === 'guest') === guest;
      return `<button class="kind-tab" type="button" role="tab" data-action="signup-kind" data-kind="${key}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${label}</button>`;
    }).join('')}</div>`;
    const panel = guest
      ? `<p class="kind-note">Use a personal email to sign up as a guest.</p><form data-form="register" novalidate>${field('email', 'Personal email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your email' })}<div class="hp" aria-hidden="true"><label>Leave this empty<input name="website" type="text" tabindex="-1" autocomplete="off"></label></div><button class="btn primary full big" type="submit">Send code</button></form>`
      : `<p class="kind-note">For LPU students and professors. Use your ${STUDENT_EXAMPLE} email.</p><form data-form="school-request" novalidate>${field('email', 'LPU email', 'email', { required: true, maxlength: 254, autocomplete: 'email', placeholder: 'Enter your ' + STUDENT_EXAMPLE })}<button class="btn primary full big" type="submit">Send code</button></form>`;
    body = `<h2>Create your account</h2><p class="auth-sub">We email a code once. LPU accounts choose a password after verification. Guests continue with the code.</p>${errorBox}${kindTabs}${panel}
      <p class="auth-switch">Already have an account? <button class="link-button" type="button" data-action="go-login">Login</button></p>`;
  } else {
    body = loginPane(errorBox, microsoft);
  }
  if(mode==='signin')body += `<p class="auth-switch"><button class="btn secondary full" type="button" data-action="go-guest">Guest · send an email code</button></p>
    ${state.config.setup_required&&launchSetupKey?'<button class="link-button" type="button" data-action="setup-admin">Set up the first CSA administrator</button>':''}`;
  const split = mode === 'signin' || mode === 'register' || mode === 'school';
  const headTitle = mode === 'code' ? 'Check Your <br>Email.'
    : mode === 'reset-request' || mode === 'reset-password' ? 'Reset Your <br>Password.'
    : mode === 'setup-admin' ? 'Set Up <br>CSA Access.'
    : onRegister ? 'Create <br>Account.'
    : 'Welcome <br>Back.';
  const authHead = `<section class="wh1128-auth-head"><h1 class="wh1128-h1">${headTitle}</h1><p class="wh1128-auth-sub">Students, professors, and CSA staff sign in with email and password. First-time LPU accounts and guests verify once with a 6-digit code.</p></section>`;
  const authAside = `<aside class="wh1128-auth-aside" aria-label="LPU Cavite CSA Lost and Found">
    <img src="/assets/wix-bag.jpg?v=244" alt="A burgundy canvas campus backpack in warm afternoon sunlight">
    <ol class="wh1128-auth-steps">
      <li>01 · Reported</li>
      <li>02 · Matched</li>
      <li>03 · Verified</li>
      <li>04 · Released</li>
    </ol>
    <p class="wh1128-auth-office">${esc(OFFICE.hours)} · Gate 1, Admin Building</p>
  </aside>`;
  if (split) {
    const loginOn = mode === 'signin';
    const signupBody = mode === 'register' || mode === 'school' ? body : signupPane(errorBox);
    const loginBody = loginOn ? body : loginPane(errorBox, microsoft);
    const authTabs = [['signin', 'Login', 'go-login'], ['register', 'Sign up', 'go-register']].map(([key, label, action]) => {
      const on = (key === 'signin') === loginOn;
      return `<button class="tab" type="button" role="tab" data-action="${action}" aria-selected="${on}" tabindex="${on ? 0 : -1}">${label}</button>`;
    }).join('');
    app.innerHTML = `${publicNav(false)}<main class="wh1128-auth" id="main" tabindex="-1">
      <div class="wh1128-wrap">${authHead}</div>
      <hr class="wh1128-rule">
      <div class="wh1128-wrap wh1128-auth-body">
        <div class="wh1128-auth-form-col">
          <div class="tabs auth-tabs" role="tablist" aria-label="Account">${authTabs}</div>
          <div class="auth-split"><section class="auth-card auth-pane${loginOn ? ' on' : ''}">${loginBody}</section><section class="auth-card auth-pane${!loginOn ? ' on' : ''}">${signupBody}</section></div>
          <p class="auth-foot"><button class="link-button" type="button" data-action="go-help">Help</button><span aria-hidden="true">·</span><button class="link-button" type="button" data-action="go-welcome">About LyFind</button></p>
        </div>
        ${authAside}
      </div>
    </main>`;
    closeMenu(false);
    finishRender();
    if (state.keepTabFocus === 'kind') document.querySelector('.kind-tab[aria-selected="true"]')?.focus();
    else if (state.keepTabFocus) document.querySelector('.auth-tabs .tab[aria-selected="true"]')?.focus();
    state.keepTabFocus = false;
    return;
  }
  app.innerHTML = `${publicNav(false)}<main class="wh1128-auth" id="main" tabindex="-1">
    <div class="wh1128-wrap">${authHead}</div>
    <hr class="wh1128-rule">
    <div class="wh1128-wrap wh1128-auth-body">
      <div class="wh1128-auth-form-col"><div class="auth-card">
        ${body}
        <p class="auth-foot"><button class="link-button" type="button" data-action="go-help">Help</button><span aria-hidden="true">·</span><button class="link-button" type="button" data-action="go-welcome">About LyFind</button></p>
      </div></div>
      ${authAside}
    </div>
  </main>`;
  closeMenu(false);
  finishRender();
  if (mode === 'code') { startResendTimer(); document.querySelector('.auth-card input[name=code]')?.focus(); }
  else if (state.keepTabFocus) { document.querySelector('.auth-card .auth-tabs .tab[aria-selected="true"]')?.focus(); state.keepTabFocus = false; }
  else document.querySelector('.auth-card input')?.focus();
}
let resendTimer;
function startResendTimer() {
  clearInterval(resendTimer);
  const tick = () => {
    const button = document.querySelector('[data-resend]');
    if (!button) { clearInterval(resendTimer); return; }
    const left = Math.ceil(((state.pending?.until || 0) - Date.now()) / 1000);
    if (left > 0) { button.disabled = true; button.textContent = `Send a new code (${left}s)`; }
    else { button.disabled = state.authBusy; button.textContent = 'Send a new code'; clearInterval(resendTimer); }
  };
  tick();
  resendTimer = setInterval(tick, 500);
}

function field(name, label, type, opts) {
  opts = opts || {};
  const required = opts.required ? 'required' : '';
  const wide = opts.wide ? ' wide' : '';
  const hint = opts.hint ? `<small>${opts.hint}</small>` : '';
  const value = opts.value ?? '';
  let control;
  if (type === 'select') {
    control = `<select name="${esc(name)}" ${required}>${(opts.options || []).map(([key, text]) => `<option value="${esc(key)}" ${String(key) === String(value) ? 'selected' : ''}>${esc(text)}</option>`).join('')}</select>`;
  } else if (type === 'textarea') {
    control = `<textarea name="${esc(name)}" ${required} maxlength="${opts.maxlength || 2000}" placeholder="${esc(opts.placeholder || '')}">${esc(value)}</textarea>`;
  } else {
    const extras = ['min', 'max', 'maxlength', 'minlength', 'accept', 'placeholder', 'autocomplete', 'inputmode', 'pattern'].filter(key => opts[key] != null).map(key => `${key}="${esc(opts[key])}"`).join(' ');
    control = `<input name="${esc(name)}" type="${esc(type)}" ${type === 'file' ? '' : `value="${esc(value)}"`} ${required} ${opts.disabled ? 'disabled' : ''} ${opts.readonly ? 'readonly tabindex="-1"' : ''} ${extras}>`;
  }
  const caption = `${label}${opts.required || opts.readonly ? '' : ' (optional)'}`;
  const locked = opts.disabled || opts.readonly ? ' locked' : '';
  return `<label class="field${wide}${locked}"><span>${caption}</span>${control}${hint}${pwError(name)}</label>`;
}
function placeFields(value, label) {
  const known = PLACES.includes(value);
  const selected = value && !known ? 'Other' : (value || '');
  const groups = PLACE_GROUPS.map(([name, places]) => `<optgroup label="${esc(name)}">${places.map(place => `<option value="${esc(place)}" ${place === selected ? 'selected' : ''}>${esc(place)}</option>`).join('')}</optgroup>`).join('');
  const select = `<select name="place" required><option value="" ${selected ? '' : 'selected'}>Choose an LPU Cavite place</option>${groups}</select>`;
  return `<label class="field"><span>${label || 'Where on campus?'}</span>${select}<small>Buildings from the campus directory, plus COECSA and L Building. Pick Other if the room is not listed.</small></label>`
    + `<div class="place-other" ${selected === 'Other' ? '' : 'hidden'}>${field('place_other', 'Other place', 'text', { required: selected === 'Other', maxlength: 200, value: known ? '' : (value || ''), placeholder: 'Building, floor, or nearby landmark' })}</div>`;
}
function colorField(value) {
  return field('color', 'Color', 'select', { required: true, value: COLORS.includes(value) ? value : '', options: [['', 'Choose a color'], ...COLORS.map(color => [color, color])] });
}
function categoryField(value) {
  return `<label class="field"><span>What kind of item?</span><select name="category" required>${categoryOptions(value, 'Choose a kind')}</select></label>`;
}
function brandFields(value) {
  const text = String(value ?? '').trim();
  const mode = !text ? 'unknown' : text === 'Unbranded' ? 'unbranded' : 'known';
  const option = (key, label) => `<option value="${key}" ${mode === key ? 'selected' : ''}>${label}</option>`;
  return `<div class="brand-field wide"><label class="field"><span>Brand</span><select name="brand_choice" data-brand-choice required>${option('unknown', "I don't know")}${option('known', 'I know the brand')}${option('unbranded', 'No brand on it')}</select><small>Leave unknown if unsure.</small></label><div class="brand-name" ${mode === 'known' ? '' : 'hidden'}>${field('brand', 'Brand name', 'text', { maxlength: 80, placeholder: 'For example, Nike', value: mode === 'known' ? text : '', disabled: mode !== 'known', required: mode === 'known' })}</div></div>`;
}
function timeField(name, label, hint) {
  return field(name, label, 'select', { value: '', options: [['', 'Not sure'], ...TIMES.filter(time => time !== 'Not sure').map(time => [time, time])], hint });
}
function dateField(name, label, opts) {
  const report = Boolean(opts.report);
  const min = report ? earliestReportDay() : opts.min;
  const max = report ? today() : opts.max;
  let value = opts.value || today();
  if (report && (value > today() || value < earliestReportDay())) value = today();
  const control = field(name, label, 'date', { required: true, value, min, max, hint: report ? '' : opts.hint });
  return `<div class="date-field">${control}</div>`;
}
function openModal(html) {
  modal.innerHTML = html;
  prepareFormAccessibility(modal);
  labelTables(modal);
  modalClosing = false;
  modal.showModal();
  const box = modal.querySelector('[data-lock]');
  const submit = modal.querySelector('button[type=submit]');
  if (box && submit) {
    submit.disabled = true;
    submit.title = box.dataset.lock || 'Confirm first';
  }
  const first = modal.querySelector('input:not([type=checkbox]):not([disabled]), textarea, select');
  first?.focus();
}
function formShell(title, text, name, body, submitLabel, context, wizard) {
  const steps = wizard ? `<ol class="wizard-steps" aria-label="Form steps">${wizard.map((label, index) => `<li class="${index === 0 ? 'now' : ''}">${index + 1}. ${label}</li>`).join('')}</ol>` : '';
  const actions = wizard
    ? `<div class="modal-actions"><button class="btn" type="button" data-action="close-modal">Cancel</button><button class="btn" type="button" data-wizard="back" hidden>Back</button><button class="btn primary" type="button" data-wizard="next">Next</button><button class="btn primary" type="submit" hidden>${submitLabel}</button></div>`
    : `<div class="modal-actions"><button class="btn" type="button" data-action="close-modal">Cancel</button><button class="btn primary" type="submit">${submitLabel}</button></div>`;
  openModal(`<div class="modal-head"><div><h2 id="modal-title">${title}</h2><p>${text}</p></div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div><form class="modal-form" data-form="${name}" data-context="${esc(JSON.stringify(context || {}))}"><div class="modal-body"><div class="form-error" hidden role="alert"></div>${steps}${body}</div>${actions}</form>`);
  window.LyFindReports?.attach(modal.querySelector('form'),{user:state.user,mode:state.config.demo_mode?'test':'live'});
}
function formSection(kicker, body) {
  return `<section class="form-section"><p class="form-kicker">${kicker}</p>${body}</section>`;
}
function lockBox(name, label, why) {
  return `<label class="check-field"><input name="${name}" type="checkbox" data-lock="${esc(why)}" required><span>${label}</span></label><p class="why submit-why">${esc(why)}</p>`;
}
function confirmAction(title, text, lock, submit, next, path, payload, message) {
  formShell(title, text, 'confirm-action', `${lockBox('confirmed', lock, 'Tick the box to continue.')}${next ? nextNote(next) : ''}`, submit, { path, payload: payload || {}, message });
}
function aiFillRow() {
  return `<div class="ai-fill-row" data-ai-fill-row hidden><button class="btn primary sm" type="button" data-action="ai-fill-photo">${svg('spark')}<span>Fill details with AI</span></button><span class="meta ai-fill-note">Let Gemini suggest the kind, color, brand, and description from this photo.</span></div>`;
}
function lostSheet(forGuest) {
  const email = forGuest ? formSection('Guest', field('guest_email', "Guest's personal email", 'email', { required: true, wide: true, maxlength: 254, autocomplete: 'email', placeholder: 'visitor@example.com', hint: 'Ask the visitor to confirm this address. If they have no Guest account yet, we email them a code and save this report when they finish.' })) : '';
  const tip = CATEGORY_TIPS.other;
  return `${email}
    ${formSection('01  /  The essentials', `${field('photo_id', 'Photo of your item', 'file', { wide: true, accept: 'image/png,image/jpeg,image/webp', hint: 'Optional quick start: pick a photo to auto-fill details with AI. JPEG, PNG, or WebP, up to 5 MB.' })}${aiFillRow()}<div class="pair">${categoryField()}${dateField('date_lost', 'When did you lose it?', { report: true })}</div>${REPORT_DATE_NOTE}${field('description', 'What did you lose?', 'textarea', { required: true, wide: true, maxlength: 2000, placeholder: `For example: ${tip[0]}.`, hint: 'Describe what it looks like, not who owns it.' })}<div class="pair">${placeFields('', 'Where was it last seen?')}${timeField('time_lost', 'About what time?', '')}</div>`)}
    ${formSection('02  /  The little details', `<div class="pair">${colorField()}${brandFields()}</div>${field('identifying_marks', 'What makes it yours?', 'textarea', { required: true, wide: true, maxlength: 2000, placeholder: tip[1], hint: 'Only CSA sees this. Write a mark, contents, or plain with no marks.' })}`)}`;
}
function lostForm() {
  formShell('Report a lost item', 'Start with the essentials. A few extra details can help CSA find a match.', 'lost', lostSheet(false), 'Submit lost report');
  modal.classList.add('sheet');
}
function guestLostForm() {
  formShell('Report for a guest', 'Save a lost report for a visitor at the desk.', 'guest-lost', lostSheet(true), 'Submit lost report');
  modal.classList.add('sheet');
}
let deskTimer = 0;
let deskCloseTimer = 0;
function stopDeskWatch() {
  clearInterval(deskTimer);
  clearTimeout(deskCloseTimer);
  deskTimer = 0;
  deskCloseTimer = 0;
}
function watchDeskHold(hold) {
  stopDeskWatch();
  const sent = hold.code_sent
    ? `We emailed a code to <b>${esc(hold.email)}</b>.`
    : `A code is already in the inbox for <b>${esc(hold.email)}</b>.`;
  const waiting = `<div class="modal-head"><div><h2 id="modal-title">Waiting for the guest</h2><p>The report stays here until they finish sign-up.</p></div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div>
    <div class="modal-body"><div class="note" role="note" id="desk-wait" data-label="At the desk"><p id="desk-status">${sent} Ask them to open LyFind, choose Sign up, then Guest, and enter that code. No password is needed. They can add their name in Account.</p><p>This report saves when they finish. You can leave this open.</p></div>
    <div class="modal-actions"><button class="btn" type="button" data-action="close-modal">Close</button></div></div>`;
  if (modal.open) { modal.innerHTML = waiting; labelTables(modal); }
  else openModal(waiting);
  modal.classList.add('sheet');
  const tick = async () => {
    try {
      const status = await api('/api/reports/desk-hold', { hold_id: hold.hold_id });
      if (status.status !== 'saved') return;
      stopDeskWatch();
      const box = document.querySelector('#desk-wait');
      if (box) box.innerHTML = '<p id="desk-status"><b>Saved.</b> They can see it when they sign in.</p>';
      await load();
      toast('Saved. They can see it when they sign in.');
      deskCloseTimer = setTimeout(() => closeModal(), 1200);
    } catch { /* keep the desk screen up and try again */ }
  };
  deskTimer = setInterval(tick, 3000);
}
function foundSheet() {
  const tip = CATEGORY_TIPS.other;
  return `${formSection('01  /  What you found', `${field('photo_id', 'Photo of the item', 'file', { wide: true, accept: 'image/png,image/jpeg,image/webp', hint: 'Optional quick start: snap or pick a photo to auto-fill details with AI. JPEG, PNG, or WebP, up to 5 MB.' })}${aiFillRow()}<div class="pair">${categoryField()}${dateField('date_found', 'When did you find it?', { report: true })}</div>${REPORT_DATE_NOTE}${field('description', 'What did you find?', 'textarea', { required: true, wide: true, maxlength: 2000, placeholder: `For example: ${tip[0]}.`, hint: 'Describe what you can see. Leave out names and ID numbers.' })}<div class="pair">${placeFields('', 'Where did you find it?')}${timeField('time_found', 'About what time?', '')}</div>`)}
    ${formSection('02  /  The little details', `<div class="pair">${colorField()}${brandFields()}</div>`)}
    ${formSection('03  /  Where is it now?', `${field('where_now', 'Where is the item now?', 'select', { required: true, wide: true, value: 'with_me', options: WHERE_NOW })}<div class="turn-in">${dateField('turn_in_deadline', 'When will you bring it to CSA?', { min: today(), value: today(), hint: '' })}</div><p class="note where-note" role="note" data-where-note>Bring it to the CSA office by this date. Matching starts once CSA receives it.</p>`)}`;
}
function foundForm() {
  if(state.user.role==='guest'){toast('Bring found items directly to the CSA office.',true);return;}
  formShell('Report a found item', 'Tell CSA what you found and where it is now. Honest details help the owner get it back.', 'found', foundSheet(), 'Submit found report');
  modal.classList.add('sheet');
}
function foundItemSheet(found) {
  const linked = found ? `<input type="hidden" name="found_report_id" value="${esc(found.id)}"><p class="note" role="note">This is the item from the found report. Confirm it is in the office.</p>` : '';
  return `${linked ? `<section class="form-section">${linked}</section>` : ''}
    ${formSection('01  /  The essentials', `${field('photo_id', 'Photo of the item', 'file', { required: true, wide: true, accept: 'image/png,image/jpeg,image/webp', hint: 'Photograph the item in front of you, then use AI to auto-fill details. JPEG, PNG, or WebP, up to 5 MB.' })}${aiFillRow()}<div class="pair">${categoryField(found?.category)}${dateField('date_found', 'Date found', { report: true, value: found?.date_found || today() })}</div>${REPORT_DATE_NOTE}${field('description', 'What is it?', 'textarea', { required: true, wide: true, maxlength: 2000, value: found?.description || '', placeholder: 'For example: a black umbrella left at the JPL lobby.' })}${placeFields(found?.place || '')}`)}
    ${formSection('02  /  For the office', `<div class="pair">${colorField(found?.color)}${brandFields(found?.brand)}</div>${field('unclaimed_after_days', 'Keep for how many days?', 'number', { required: true, value: 30, min: 1, max: 3650, hint: 'Most items are kept 30 days.' })}${field('private_details', 'Private details', 'textarea', { required: true, wide: true, maxlength: 3000, hint: 'Only staff see this. Use it to check the owner.' })}${nextNote('The item shows in Found items, and matching runs right away.')}`)}`;
}
function receiveForm(found) {
  formShell('Receive item', 'Use this only after the item is physically in the office.', 'receive', foundItemSheet(found)+'<label class="check-field"><input name="board_published" type="checkbox"><span>List the general category and found week on Found items.</span></label>', 'Receive item');
  modal.classList.add('sheet');
}
function nextNote(text) {
  return `<p class="note next-note" role="note" data-label="What happens next">${text}</p>`;
}
function claimForm(match) {
  if (!match) return;
  formShell('Claim item', 'Describe something only the owner would know. CSA compares it with the item.', 'claim', `<p class="note" role="note" data-label="How you get it back">Answer these questions correctly, then show a valid ID at the CSA office. CSA never hands an item over without ID.</p>${field('details', 'What proves it is yours?', 'textarea', { required: true, minlength: 3, maxlength: 3000, hint: 'A mark, the contents, or a label. Do not type a password.' })}<label class="check-field"><input name="consent" type="checkbox" required><span>I agree to send these answers to CSA.</span></label>${nextNote('CSA reads your answers. You will see an update here when they decide.')}`, 'Send', { item_id: match.item_id, report_id: match.report_id });
}
function decisionForm(id, stage, passed) {
  const office = stage === 'in-person';
  const title = passed ? (office ? 'Pass the office check?' : 'Pass the online check?') : 'Reject this claim?';
  const text = passed
    ? (office ? 'You checked the owner’s ID and answers in person.' : 'The answers match what you know about the item.')
    : 'Tell the owner what happened and what they can do next.';
  const next = passed
    ? (office ? 'The claim moves to Hand over. You add three photos, then give the item to the owner.' : 'The owner is told to bring their ID to the CSA office.')
    : 'The owner reads your reason. The item goes back to the office shelf. They have 3 tries per item.';
  formShell(title, text, 'decision', `${field('reason', passed ? 'Notes' : 'Reason', 'textarea', { required: !passed, maxlength: 2000, hint: passed ? 'Optional. What matched?' : 'Required. The owner will see this.' })}${lockBox('checked', passed ? 'I checked this myself.' : 'I want to reject this claim.', 'Tick the box to continue.')}${nextNote(next)}`, passed ? (office ? 'Pass office check' : 'Pass online check') : 'Reject', { claim_id: id, stage, passed });
}
function consentForm(id) {
  formShell('Start the office check?', 'The owner must be at the office. Tell them you will take three photos: the owner with the item, their ID, and their signature.', 'consent', `${field('purpose', 'What you told the owner', 'textarea', { required: true, value: 'To check ownership and record the handover' })}${lockBox('in_person', 'The owner is here and agrees to the photos.', 'Tick the box to continue.')}${nextNote('You can then pass the office check, or reject the claim.')}`, 'Start office check', { claim_id: id });
}
function approveForm(id) {
  const claim = arr('claims').find(item => String(item.id) === String(id));
  if (!claim?.consent_at && !claim?.in_person_consent) { toast('Press Start office check first.', true); return; }
  formShell('Approve the handover?', 'The owner must show a valid ID at the office. Add the three photos, then confirm. You hand the item over as a separate step.', 'approve', `
    <div class="wizard-step">${field('claimant_photo', 'Owner with the item', 'file', { required: true, accept: 'image/png,image/jpeg,image/webp' })}${field('id_photo', 'ID photo', 'file', { required: true, accept: 'image/png,image/jpeg,image/webp' })}${field('signature', 'Signature', 'file', { required: true, accept: 'image/png,image/jpeg,image/webp', hint: 'JPEG, PNG, or WebP, up to 5 MB each.' })}</div>
    <div class="wizard-step" hidden>${field('handover_note', 'Note', 'textarea', { maxlength: 2000 })}${lockBox('verified', 'I checked the person, the photos, and both checks.', 'Tick the box to continue.')}${nextNote('The owner is told they can pick up the item. Then you press Hand over item.')}</div>`, 'Approve handover', { claim_id: id }, ['Photos', 'Confirm']);
}
function releaseForm(id) {
  const claim = arr('claims').find(item => String(item.id) === String(id));
  const item = claim ? claimTitle(claim) : 'this item';
  const who = firstName(claim?.claimant_name);
  formShell('Hand over the item?', `Check the owner’s ID against the photo first. ${item} will be recorded as given to ${who}. This cannot be undone.`, 'release', `${lockBox('confirmed', 'The owner has the item now.', 'Tick the box to continue.')}${nextNote('The claim and the report close, and the owner is told.')}`, 'Hand over item', { claim_id: id });
}
function staffForm(person) {
  formShell(person ? 'Edit staff access' : 'Add staff', 'Only an existing administrator can add staff.', 'staff', `${field('name', 'Full name', 'text', { required: true, value: person?.name || '', maxlength: 120 })}${field('email', 'Email', 'email', { required: true, value: person?.email || '', maxlength: 250 })}${person ? '<p class="meta">Leave the password empty to keep the current one.</p>' : ''}${passwordSet(PW_MIN, true, Boolean(person))}${person ? field('active', 'Access', 'select', { required: true, value: String(Boolean(person.active)), options: [['true', 'Active'], ['false', 'Inactive']] }) : ''}`, 'Save', { action: person ? 'update' : 'create', user_id: person?.id });
  const box = modal.querySelector('[data-pw-set]');
  if (box) updatePasswordHelper(box);
}
function hideForm(kind, id) {
  formShell('Hide this report?', 'Use this for spam or pranks. The record stays in the database and the log. You can show it again later.', 'review', `${field('reason', 'Reason', 'textarea', { required: true, maxlength: 500, hint: 'Other staff will see this in the activity log.' })}${lockBox('confirmed', 'I want to hide this report.', 'Tick the box to continue.')}${nextNote('The owner and matching stop seeing it. Nothing is deleted.')}`, 'Hide report', { kind, id, action: 'hide' });
}
function setPersonPasswordForm(person) {
  if (!person || person.role === 'admin') return;
  formShell(`Set password for ${esc(person.name)}`, `${esc(person.email)} must show a valid ID at the desk. LyFind will not email this password.`, 'set-person-password',
    `<input type="hidden" name="name" value="${esc(person.name)}"><input type="hidden" name="email" value="${esc(person.email)}">${passwordSet(PW_MIN, true)}<p class="note" role="note">Tell them the new password once. It is not shown again, and it is not written in the log.</p>`,
    'Set password', { user_id: person.id });
  const box = modal.querySelector('[data-pw-set]');
  if (box) updatePasswordHelper(box);
}
function blockForm(person) {
  if (!person) return;
  formShell(`Block ${esc(person.name)}?`, `${esc(person.email)} is signed out now and cannot sign in. Their records stay.`, 'block', `${field('reason', 'Reason', 'textarea', { required: true, maxlength: 500, hint: 'Other staff will see this in the activity log.' })}${lockBox('confirmed', 'I want to block this account.', 'Tick the box to continue.')}${nextNote('They see a neutral message when they try to sign in. You can unblock them later.')}`, 'Block account', { user_id: person.id, blocked: true });
}
function rosterForm() {
  formShell('Add an allowed email', 'This person can then open an account with a code sent to this email, and sign in with a password after that.', 'roster-add', `${field('email', 'School email', 'email', { required: true, maxlength: 254, placeholder: STUDENT_EXAMPLE, hint: 'The student number is filled in from this email.' })}${field('name', 'Name', 'text', { maxlength: 120 })}${field('student_number', 'Student number', 'text', { maxlength: 40 })}${field('role', 'Role', 'select', { required: true, value: 'student', options: [['student', 'Student'], ['professor', 'Professor']] })}`, 'Add email', {});
}
let rosterDraft=null;
function rosterImportForm() {
  rosterDraft=null;
  formShell('Import allowed emails', 'Choose a CSV file. The first row names the columns: email (required), name, student_number, role (student or professor).', 'roster-import', `${field('csv', 'CSV file', 'file', { required: true, wide: true, accept: '.csv,text/csv', hint: 'Preview the names, roles, and addresses before confirming.' })}`, 'Preview accounts', {});
}
function confirmMatch(id, confirmed) {
  formShell(confirmed ? 'Approve this match?' : 'Reject this match?', confirmed ? 'Check the photos and the private details first.' : 'It is not the same item.', 'match-decision', `${lockBox('confirmed', confirmed ? 'I checked the details.' : 'I want to reject this match.', 'Tick the box to continue.')}${nextNote(confirmed ? 'The owner is told, and is asked to answer a few questions. Their claim shows up in Claims.' : 'The owner is not told. The item stays in the office for other matches.')}`, confirmed ? 'Approve match' : 'Reject', { match_id: id, confirmed });
}
function showDone(claim) {
  const item = claim ? claimTitle(claim) : 'The item';
  const who = firstName(claim?.claimant_name);
  const when = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  openModal(`<div class="modal-body closure"><p class="kicker">Handed back</p><h2 id="modal-title">Done.</h2><p>The ${esc(item)} was handed to ${esc(who)} on ${esc(when)}.</p><p class="muted">The lost report is closed. Nobody else can claim this item.</p><div class="modal-actions"><button class="btn primary" type="button" data-action="close-modal">Done</button></div></div>`);
}
function recordSheet(title, statusHtml, body, actions) {
  const row = actions || button('Close', 'close-modal', '', 'primary');
  openModal(`<div class="modal-head"><div><h2 id="modal-title">${esc(title)}</h2>${statusHtml}</div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div><div class="modal-body">${body}</div><div class="modal-actions">${row}</div>`);
}
function sheetActions(primary, extras) {
  const side = extras.filter(Boolean).join('');
  const close = button('Close', 'close-modal', '', primary ? 'secondary' : 'primary');
  if (!side) return `${close}${primary || ''}`;
  return `<div class="action-side">${side}</div><div class="action-main">${close}${primary || ''}</div>`;
}
function recordPhoto(id, alt) {
  return id ? `<img class="detail-photo" alt="${esc(alt)}" src="/api/files/${encodeURIComponent(id)}">` : '';
}
function looksLine(row) {
  const looks = [catName(row.category), row.color, row.brand && row.brand !== 'Unbranded' ? row.brand : ''].filter(Boolean).map(esc).join(' · ');
  return `<p class="detail-looks">${looks || esc(catName(row.category))}</p>`;
}
function showReport(report) {
  if (!report) { toast('That report is not on this screen.', true); return; }
  const staff = admin();
  const desk = staff ? lostDesk(report) : null;
  const marks = staff || report.identifying_marks ? `<div class="private-box"><span class="kicker">What makes it yours</span><p>${esc(report.identifying_marks || 'None recorded.')}</p>${staff ? '<p class="muted">Only CSA sees this. Compare it with the claimant’s answers.</p>' : ''}</div>` : '';
  const who = staff ? whoLine('Reported by', report.owner_name || 'Owner', report.owner_role, report.owner_email, report.owner_phone, report.owner_number) : '';
  const next = staff ? `<p class="note" role="note" data-label="What happens next">${esc(desk.next)}</p>` : '';
  const progress = staff ? staffSteps(reportStage(report), true) : tracker(sourceForReport(report));
  const body = `<div class="sheet-block">${recordPhoto(report.photo_id, 'Photo from the report')}${looksLine(report)}<p class="meta">${esc(report.place || 'Campus')}</p>${dateLine(report.date_lost, 'Date lost')}${timeLine(report.time_lost)}${staff ? dateLine(report.created_at, 'Filed') : ''}${reportTags(report)}${who}${progress}${next}${marks}${staff ? matchSummary(desk.related, 'report') : ''}</div>`;
  recordSheet(report.description, badge(report), body, staff ? sheetActions(desk.primary, [desk.hide]) : '');
}
function showFoundReport(report) {
  if (!report) { toast('That report is not on this screen.', true); return; }
  const staff = admin();
  const desk = staff ? foundDesk(report) : null;
  const now = report.where_now || 'with_me';
  const where = WHERE_TEXT[now] ? WHERE_TEXT[now][staff ? 0 : 1] : '';
  const who = staff ? whoLine('Reported by', report.finder_name || 'a finder', report.finder_role, report.finder_email, report.finder_phone, '') : '';
  const noteText = { with_me: 'Bring this item to the CSA office. It cannot be claimed until then.', security: 'CSA will collect this from campus security. It cannot be claimed until it reaches the office.', left: 'CSA may check the place you named. It cannot be claimed until it reaches the office.' }[now];
  const next = staff ? `<p class="note" role="note" data-label="What happens next">${esc(desk.next)}</p>` : (report.status === 'awaiting_turn_in' ? `<p class="note" role="note">${noteText}</p>` : '');
  const when = `${dateLine(report.date_found, 'Date found')}${timeLine(report.time_found)}${report.status === 'awaiting_turn_in' && now === 'with_me' ? dateLine(report.turn_in_deadline, 'Bring in by') : ''}${staff ? dateLine(report.created_at, 'Filed') : ''}`;
  const hidden = report.hidden ? '<div class="pills"><span class="tag">Hidden</span></div>' : '';
  const body = `<div class="sheet-block">${recordPhoto(report.photo_id, 'Photo from the found report')}${looksLine(report)}<p class="meta">${esc(report.place || 'Campus')}</p>${where ? `<p class="meta">${esc(where)}</p>` : ''}${when}${hidden}${who}${next}</div>`;
  recordSheet(report.description, badge(report), body, staff ? sheetActions(desk.primary, [desk.hide]) : '');
}
function showItem(item) {
  if (!item) { toast('That item is not on this screen.', true); return; }
  const staff = admin();
  const desk = staff ? itemDesk(item) : null;
  const secret = staff ? `<div class="private-box"><span class="kicker">Private details</span><p>${esc(item.private_details || 'None recorded.')}</p><p class="muted">Do not read these details aloud to the claimant. Compare them with the answers.</p></div>` : '';
  const who = staff && item.recorded_by_name ? `<p class="meta">Received by <b>${esc(item.recorded_by_name)}</b></p>` : '';
  const next = staff ? `<p class="note" role="note" data-label="What happens next">${esc(desk.next)}</p>` : '';
  const progress = staff ? staffSteps(itemStage(item), true) : '';
  const body = `<div class="sheet-block">${recordPhoto(item.photo_id, 'Photo of the item, staff only')}${looksLine(item)}<p class="meta">${esc(item.place || 'Campus')}</p>${dateLine(item.date_found, 'Date found')}${item.received_at ? dateLine(item.received_at, 'Received') : ''}${who}${progress}${next}${staff?`<button class="btn secondary" type="button" data-action="toggle-board" data-id="${item.id}" data-published="${!item.board_published}">${item.board_published?'Remove from Found items':'List on Found items'}</button>`:''}${secret}${staff ? matchSummary(desk.related, 'item') : ''}</div>`;
  recordSheet(item.description, badge(item), body, staff ? sheetActions(desk.primary, []) : '');
}
function showMatch(match) {
  if (!match) { toast('That match is not on this screen.', true); return; }
  const needsCheck = match.status === 'suggested' && match.report_flagged;
  const photo = (id, label) => id ? `<figure class="photo-box"><img src="/api/files/${encodeURIComponent(id)}" alt="${esc(label)}, visible to staff only"><figcaption>${esc(label)}</figcaption></figure>` : '';
  const photos = match.report_photo_id || match.item_photo_id ? `<div class="photo-pair">${photo(match.report_photo_id, 'Owner’s photo')}${photo(match.item_photo_id, 'Item in the office')}</div>` : '';
  const guest = match.owner_role === 'guest' ? ' · Guest' : '';
  let primary = '';
  let next = 'The owner answers the questions. Their claim shows up in Claims.';
  if (needsCheck) { primary = button('Check report', 'check-report', match.report_id, 'primary'); next = 'A guest sent this report. Check it first, then you can approve the match.'; }
  else if (match.status === 'suggested') { primary = button('Approve match', 'confirm-match', match.id, 'primary'); next = 'Approve to invite the owner to answer questions, or reject it if it is not the same item.'; }
  const reject = match.status === 'suggested' ? button('Reject', 'dismiss-match', match.id, 'danger') : '';
  const score = `<span class="score-pill ${match.level === 'strong' ? 'strong' : 'possible'}">${matchLabel(match)}</span>`;
  const body = `<div class="sheet-block"><div class="match-score">${score}</div><p class="meta">Owner: <b>${esc(match.owner_name || 'Owner')}</b>${esc(guest)} · ${esc(match.report_description || 'Lost report')}</p><p class="meta">${esc(match.report_place || 'Campus')}${match.report_color ? ` · ${esc(match.report_color)}` : ''}</p>${dateLine(match.date_lost, 'Date lost')}${photos}${matchWhy(match)}<p class="note" role="note" data-label="What happens next">${esc(next)}</p>${match.private_details ? `<div class="private-box"><span class="kicker">Private details</span><p>${esc(match.private_details)}</p><p class="muted">Do not read these details aloud to the claimant. Compare them with the answers.</p></div>` : ''}</div>`;
  const extras = [button('View report', 'open-lost', match.report_id, 'secondary'), button('View item', 'view-item', match.item_id, 'secondary'), reject];
  recordSheet(match.item_description || 'Match', badge({ status: match.status }), body, sheetActions(primary, extras));
}
function openRecord(kind, id) {
  if (kind === 'lost') return showReport(arr('reports').find(report => String(report.id) === String(id)));
  if (kind === 'found') return showFoundReport(arr('found_reports').find(report => String(report.id) === String(id)));
  if (kind === 'item') return showItem(arr('items').find(item => String(item.id) === String(id)));
  if (kind === 'match') return showMatch(arr('matches').find(row => String(row.id) === String(id)));
  return false;
}
function moveWizard(button) {
  const form = button.closest('form');
  const steps = [...form.querySelectorAll('.wizard-step')];
  const current = steps.findIndex(step => !step.hidden);
  const forward = button.dataset.wizard === 'next';
  if (forward && !stepValid(steps[current])) return;
  const next = current + (forward ? 1 : -1);
  if (next < 0 || next >= steps.length) return;
  steps.forEach((step, index) => { step.hidden = index !== next; });
  form.querySelectorAll('.wizard-steps li').forEach((item, index) => { item.className = index < next ? 'done' : index === next ? 'now' : ''; });
  form.querySelector('[data-wizard="back"]').hidden = next === 0;
  const last = next === steps.length - 1;
  form.querySelector('[data-wizard="next"]').hidden = last;
  form.querySelector('button[type=submit]').hidden = !last;
  if (last) fillSummary(form);
  steps[next].querySelector('input,select,textarea')?.focus();
}
function stepValid(step) {
  prepareFormAccessibility(step);
  const fields = [...step.querySelectorAll('input,select,textarea')].filter(el => !el.disabled && !el.closest('[hidden]'));
  const errors = Object.fromEntries(fields.filter(el => el.name && !el.checkValidity()).map(el => [el.name, el.validationMessage]));
  if (Object.keys(errors).length) {
    if (!showFieldErrors(step, errors)) fields.find(el => !el.checkValidity())?.reportValidity();
    return false;
  }
  return true;
}
function fillSummary(form) {
  const box = form.querySelector('.wizard-summary');
  if (!box) return;
  const data = Object.fromEntries(new FormData(form).entries());
  const place = data.place === 'Other' ? data.place_other : data.place;
  const when = data.date_lost ? `Date lost ${dateText(data.date_lost)}` : data.date_found ? `Date found ${dateText(data.date_found)}` : '';
  const bits = [catName(data.category), data.description, place, data.color, when].filter(Boolean);
  box.innerHTML = `<p class="kicker">Check this</p><p>${esc(bits.join(' · '))}</p>`;
}
function closeModal() {
  if (!modal.open || modalClosing) return;
  modal.querySelectorAll('form[data-report-stage]').forEach(form=>window.LyFindReports?.flush(form));
  stopDeskWatch();
  modal.classList.remove('sheet');
  modal.close();
  modal.innerHTML = '';
  fileUrls.forEach(url => URL.revokeObjectURL(url));
  fileUrls.clear();
  const drafts=document.querySelector('[data-report-drafts]');
  if(drafts)drafts.innerHTML=reportDraftNotice();
}
function validateImage(file, required) {
  if (!file || !file.size) { if (required) throw new Error('Choose a photo to continue.'); return; }
  if (file.size > 5 * 1024 * 1024) throw new Error('That photo is too big. Choose one that is 5 MB or smaller.');
  const type = String(file.type || '').toLowerCase();
  const name = String(file.name || '').toLowerCase();
  const okType = ['image/png', 'image/jpeg', 'image/jpg', 'image/pjpeg', 'image/webp'].includes(type);
  const okName = /\.(jpe?g|png|webp)$/.test(name);
  if (okType || (!type && okName)) return;
  throw new Error('Use a JPEG, PNG, or WebP photo. Other file types are not accepted.');
}
function previewFile(input) {
  const fieldEl = input.closest('.field');
  fieldEl?.querySelector('.file-preview')?.remove();
  fieldEl?.querySelectorAll('[data-error-for]').forEach(item => { item.hidden = true; item.textContent = ''; });
  input.removeAttribute('aria-invalid');
  const file = input.files?.[0];
  if (!file) return;
  try { validateImage(file, true); }
  catch (error) {
    input.value = '';
    const form = input.closest('form');
    if (!form || !showFieldErrors(form, { [input.name]: error.message })) toast(error.message, true);
    return;
  }
  const url = URL.createObjectURL(file);
  fileUrls.add(url);
  const preview = document.createElement('div');
  preview.className = 'file-preview';
  preview.innerHTML = `<img alt="Selected photo preview" src="${url}"><span>${esc(file.name)}</span>`;
  fieldEl?.append(preview);
}
async function upload(file, kind, claimId) {
  if (!file?.size) return null;
  validateImage(file, true);
  const content = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('This image could not be read.'));
    reader.readAsDataURL(file);
  });
  return (await api('/api/uploads', { name: file.name, mime: file.type, content, kind, ...(claimId ? { claim_id: claimId } : {}) })).id;
}
function readPlace(data) {
  if (data.place === 'Other') data.place = data.place_other || '';
  delete data.place_other;
  return data;
}
function openTask(task) {
  state.taskKey = task.key;
  state.focusId = task.el;
  state.view = task.view;
  state.query = '';
  state.quick = null;
  const waitingList = waitingClaims();
  const isWaiting = waitingList.some(claim => String(claim.id) === String(task.id));
  state.tab.claims = isWaiting ? 'needs' : 'finished';
  const pool = isWaiting ? waitingList : arr('claims').filter(claim => ['released', 'rejected'].includes(claim.status));
  state.page = {};
  state.page.claims = Math.floor(Math.max(0, pool.findIndex(claim => String(claim.id) === String(task.id))) / PAGE_SIZE) + 1;
  render();
}
function showLoginError(message) {
  const el = document.querySelector('.auth-pane.on [data-auth-error]') || document.querySelector('[data-auth-error]');
  if (!el) { toast(message, true); return; }
  el.hidden = false;
  el.className = 'form-error';
  el.innerHTML = statusMarkup(message, 'error');
}
function setAuthBusy(busy) {
  state.authBusy = busy;
  document.querySelectorAll('.auth-card button, .auth-card .btn').forEach(el => { el.disabled = busy; });
}

function resetSession() {
  state.user = null;
  state.data = {};
  state.screen = 'welcome';
  state.authMode = 'signin';
  state.view = 'home';
  state.query = '';
  state.page = {};
  state.filter = '';
  state.quick = null;
  state.taskKey = null;
  state.focusId = null;
  state.intent = null;
  state.pending = null;
  state.flash = null;
  state.category = '';
  state.tab = { desk: 'all', items: 'office', office: 'staff', reports: 'lost', claims: 'needs', matches: 'review', lost: 'need', mine: 'open', myclaims: 'invites' };
}

document.addEventListener('toggle', event => {
  const menu = event.target;
  if (!menu.matches?.('details.more')) return;
  if (menu.open) document.querySelectorAll('details.more[open]').forEach(other => { if (other !== menu) other.open = false; });
  placeMoreMenu(menu);
}, true);
document.addEventListener('scroll', event => {
  const open = document.querySelector('details.more[open]');
  if (!open) return;
  if (event.target?.contains?.(open) || event.target === document || event.target === document.documentElement) placeMoreMenu(open);
}, true);
window.addEventListener('resize', () => { const open = document.querySelector('details.more[open]'); if (open) placeMoreMenu(open); });
let deskGesture = null;
document.addEventListener('pointerdown', event => {
  const row = event.target.closest?.('.desk-row');
  if (!row) { deskGesture = null; return; }
  const scroller = row.closest('.desk-scroll');
  deskGesture = { row, x: event.clientX, y: event.clientY, top: scroller ? scroller.scrollTop : 0 };
}, true);
document.addEventListener('click', event => {
  const row = event.target.closest?.('.desk-row');
  if (!row || !deskGesture || deskGesture.row !== row) return;
  const scroller = row.closest('.desk-scroll');
  const moved = Math.abs(event.clientX - deskGesture.x) > 8 || Math.abs(event.clientY - deskGesture.y) > 8 || (scroller && Math.abs(scroller.scrollTop - deskGesture.top) > 2);
  deskGesture = null;
  if (moved) { event.preventDefault(); event.stopPropagation(); }
}, true);
document.addEventListener('click', async event => {
  const wizardButton = event.target.closest('[data-wizard]');
  if (wizardButton) { moveWizard(wizardButton); return; }
  document.querySelectorAll('details.more[open]').forEach(menu => { if (!menu.contains(event.target) || event.target.closest('.menu-item')) menu.open = false; });
  const guideTab = event.target.closest('[data-guide-tab]');
  if (guideTab) {
    const box = guideTab.closest('[data-guide]');
    box.querySelectorAll('[data-guide-tab]').forEach(tab => { const on = tab === guideTab; tab.setAttribute('aria-selected', String(on)); tab.tabIndex = on ? 0 : -1; });
    box.querySelectorAll('.guide-panel').forEach(panel => { panel.hidden = panel.id !== guideTab.getAttribute('aria-controls'); });
    if (state.keepTabFocus) { guideTab.focus(); state.keepTabFocus = false; }
    return;
  }
  const group = event.target.closest('[data-tab-group]');
  if (group) { state.tab[group.dataset.tabGroup] = group.dataset.tabValue; state.page = {}; state.query = ''; state.quick = null; render(); if (state.keepTabFocus) { document.querySelector('.tab[aria-selected="true"]')?.focus({ preventScroll: true }); state.keepTabFocus = false; } return; }
  const pageButton = event.target.closest('[data-page-key]');
  if (pageButton && !pageButton.disabled) {
    const key = pageButton.dataset.pageKey;
    state.page[key] = (state.page[key] || 1) + Number(pageButton.dataset.dir);
    render();
    return;
  }
  const quickCard = event.target.closest('[data-quick]');
  if (quickCard) { openQuick(quickCard.dataset.quick); return; }
  const hashLink = event.target.closest('a[href^="#"]');
  if (hashLink && hashLink.closest('.help-jump')) {
    const target = document.querySelector(hashLink.getAttribute('href'));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ block: 'start' });
    }
    return;
  }
  if (hashLink && document.querySelector('.pub-drawer.open, .sidebar.open')) closeMenu(false);
  const sheet = event.target.closest('[data-sheet]');
  if (sheet && !event.target.closest('button, a, summary, details, input, select, textarea, label')) { openRecord(sheet.dataset.sheet, sheet.dataset.id); return; }
  const nav = event.target.closest('[data-nav]');
  if (nav) {
    const dest = nav.dataset.navTab || '';
    const split = dest.indexOf(':');
    state.view = nav.dataset.nav;
    state.query = '';
    state.category = '';
    state.page = {};
    state.quick = null;
    state.filter = '';
    if (state.view !== 'account') state.flash = null;
    if (split > 0) state.tab[dest.slice(0, split)] = dest.slice(split + 1);
    closeMenu(false);
    render();
    if (event.detail === 0) {
      const heading = document.querySelector('#main h1');
      if (heading) { heading.tabIndex = -1; heading.focus(); }
    }
    return;
  }
  const el = event.target.closest('[data-action]');
  if (!el || el.disabled) return;
  const action = el.dataset.action;
  const id = el.dataset.id;
  try {
    if(action==='report-draft'){if(id==='found')foundForm();else lostForm();modal.querySelector('[data-resume-draft]')?.click();return;}
    if(action==='retry-dashboard'){
      el.disabled=true;
      try{await load();toast('Dashboard updated.');}catch(error){savedRefreshNotice();}finally{el.disabled=false;}
      return;
    }
    if (action === 'search-open') { state.view = id || 'today'; render(); return; }
    if (action === 'home') { if (state.user) { state.view = admin() ? 'today' : 'home'; render(); } return; }
    if (action === 'go-help') {
      if (state.user) { state.view = 'help'; closeMenu(false); render(); } else { state.screen = 'help'; render(); }
      window.scrollTo(0, 0);
      return;
    }
    if (action === 'go-welcome') { state.screen = 'welcome'; render(); window.scrollTo(0, 0); return; }
    if (action === 'go-section') {
      const section = el.dataset.section;
      state.screen = 'welcome';
      closeMenu(false);
      render();
      document.getElementById(section)?.scrollIntoView({ block: 'start' });
      return;
    }
    if (action === 'show-password') {
      const form = document.querySelector('#password-form');
      const note = document.querySelector('#forgot-note');
      if (note) note.hidden = true;
      if (form) { form.hidden = false; form.querySelector('input')?.focus(); }
      return;
    }
    if (action === 'open-staff') {
      state.view = 'office';
      state.tab.office = 'staff';
      closeMenu(false);
      render();
      window.scrollTo(0, 0);
      return;
    }
    if (action === 'forgot-password') {
      const note = document.querySelector('#forgot-note');
      const form = document.querySelector('#password-form');
      if (form) form.hidden = true;
      if (note) { note.hidden = false; note.scrollIntoView({ block: 'nearest' }); }
      return;
    }
    if (action === 'password-policy') { passwordPolicy(el); return; }
    if (action === 'go-login' || action === 'go-register') {
      if (state.authBusy) return;
      if (state.screen === 'auth') state.keepTabFocus = true;
      state.screen = 'auth';
      state.pending = null;
      state.authMode = action === 'go-login' ? 'signin' : 'register';
      render();
      window.scrollTo(0, 0);
      return;
    }
    if (action === 'signup-kind') {
      if (state.authBusy) return;
      state.signupKind = el.dataset.kind === 'guest' ? 'guest' : 'lpu';
      state.screen = 'auth';
      state.authMode = 'register';
      state.keepTabFocus = 'kind';
      render();
      return;
    }
    if(action==='go-guest'){
      state.screen='auth';state.authMode='register';state.signupKind='guest';state.pending=null;render();return;
    }
    if(action==='setup-admin'){state.screen='auth';state.authMode='setup-admin';render();return;}
    if(action==='open-testing'){
      await openTestingWorkspace();return;
    }
    if (action === 'toggle-theme') { applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'); return; }
    if (action === 'open-accessibility') { window.LyFindAccessibility?.open(); return; }
    if (action === 'quick-testing') {
      el.disabled = true;
      try { await quickTesting(); } finally { el.disabled = false; }
      return;
    }
    if (action === 'test-account') {
      if (!state.config.demo_mode) return;
      const buttons = [...modal.querySelectorAll('[data-action="test-account"]')];
      buttons.forEach(button => { button.disabled = true; });
      try {
        const result = await api('/api/auth/demo', { role: id });
        resetSession();
        state.user = result.user;
        state.csrf = result.csrf_token;
        state.view = admin() ? 'today' : 'home';
        closeModal();
        app.replaceChildren(); // A different role needs fresh navigation, not the previous account's sidebar.
        await load();
        toast('Testing as ' + state.user.name + '.');
      } finally { buttons.forEach(button => { button.disabled = false; }); }
      return;
    }
    if (action === 'go-reset') { if (state.authBusy) return; state.screen = 'auth'; state.authMode = 'reset-request'; state.pending = null; render(); window.scrollTo(0, 0); return; }
    if (action === 'go-school') { if (state.authBusy) return; state.screen = 'auth'; state.authMode = 'register'; state.signupKind = 'lpu'; state.pending = null; render(); window.scrollTo(0, 0); return; }
    if (action === 'change-email') { if (state.authBusy) return; if (state.pending?.kind === 'reset') { state.authMode = 'reset-request'; state.pending = null; render(); return; } state.signupKind = state.pending?.kind === 'signup' ? 'guest' : 'lpu'; state.authMode = 'register'; state.pending = null; render(); return; }
    if (action === 'resend-code') {
      const current = state.pending;
      if (!current || state.authBusy) return;
      setAuthBusy(true);
      try {
        const reply = current.kind === 'reset'
          ? await api('/api/auth/reset/request', { email: current.email })
          : current.kind === 'school'
            ? await api('/api/auth/school/request', { email: current.email })
            : await api('/api/auth/guest/request', { email: current.email });
        state.pending = { ...current, demo_code:reply.demo_code, until: Date.now() + (reply.resend_in || 60) * 1000 };
        render();
        toast(current.kind === 'school' ? 'A new code was sent to your Outlook inbox.' : 'A new code was sent to your email.', 'wait');
      } finally { setAuthBusy(false); startResendTimer(); }
      return;
    }
    if (action === 'set-theme') { applyTheme(el.dataset.theme); return; }
    if (action === 'toggle-pw') {
      const input = el.closest('.pw').querySelector('input');
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      const what = (el.closest('label')?.querySelector(':scope > span')?.textContent || 'password').toLowerCase();
      el.innerHTML = `<span class="pw-eye">${svg(show ? 'eyeoff' : 'eye')}</span>`;
      el.setAttribute('aria-pressed', String(show));
      el.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} ${what}`);
      el.title = `${show ? 'Hide' : 'Show'} ${what}`;
      return;
    }
    if (action === 'reload') return location.reload();
    if (action === 'menu') return toggleMenu();
    if (action === 'menu-close') return closeMenu();
    if (action === 'close-modal') { if (!modal.querySelector('form[data-submitting="true"]')) { closeModal(); if (admin()) { state.view = state.view || 'today'; } } return; }
    if (action === 'logout') {
      return formShell('Sign out?', 'You can sign back in with the same email.', 'logout',
        '<p class="muted">Sign out of LyFind. Your reports and claims stay saved.</p>', 'Sign out', {});
    }
    if (action === 'switch-account') {
      return formShell('Switch account?', 'This signs out, then opens Login for a different email.', 'switch-account',
        '<p class="muted">Reports and claims stay saved on this account.</p>', 'Switch account', {});
    }
    if (action === 'lost') return lostForm();
    if (action === 'guest-lost') return guestLostForm();
    if (action === 'found') return foundForm();
    if (action === 'receive') return receiveForm();
    if (action === 'receive-found') return receiveForm(arr('found_reports').find(report => String(report.id) === String(id)));
    if (action === 'view-item') return showItem(arr('items').find(item => String(item.id) === String(id)));
    if (action === 'claim') return claimForm(arr('matches').find(match => String(match.id) === String(id)));
    if (action === 'online-pass') return decisionForm(id, 'online', true);
    if (action === 'online-reject') return decisionForm(id, 'online', false);
    if (action === 'inperson-pass') return decisionForm(id, 'in-person', true);
    if (action === 'inperson-reject') return decisionForm(id, 'in-person', false);
    if (action === 'consent') return consentForm(id);
    if (action === 'approve') return approveForm(id);
    if (action === 'release') return releaseForm(id);
    if (action === 'confirm-match') return confirmMatch(id, true);
    if (action === 'dismiss-match') return confirmMatch(id, false);
    if (action === 'check-report') {
      return confirmAction('Mark this guest report as checked?', 'Matching waits until you do this. Hide it instead if it looks like a prank.',
        'This report looks real.', 'Check report', 'Matching can then compare it with items in the office.',
        '/api/reports/review', { kind: 'lost', id, action: 'checked' }, 'Report checked. Matching can go ahead.');
    }
    if (action === 'hide-report') return hideForm('lost', id);
    if (action === 'hide-found') return hideForm('found', id);
    if (action === 'unhide-report' || action === 'unhide-found') {
      const kind = action === 'unhide-report' ? 'lost' : 'found';
      return confirmAction('Show this report again?', 'It will be visible to matching and to the owner again.',
        'Show this report again.', 'Show again', '',
        '/api/reports/review', { kind, id, action: 'unhide' }, 'The report is visible again.');
    }
    if (action === 'set-person-password') return setPersonPasswordForm(arr('people').find(person => String(person.id) === String(id)));
    if (action === 'block-user') return blockForm(arr('people').find(person => String(person.id) === String(id)));
    if (action === 'unblock-user') {
      const person = arr('people').find(row => String(row.id) === String(id));
      return confirmAction(`Unblock ${esc(person?.name || 'this account')}?`, `${esc(person?.email || 'This person')} will be able to sign in again.`,
        'Unblock this account.', 'Unblock', '',
        '/api/users/block', { user_id: id, blocked: false, reason: '' }, 'Account unblocked.');
    }
    if (action === 'add-roster') return rosterForm();
    if (action === 'import-roster') return rosterImportForm();
    if (action === 'toggle-roster') {
      const row = arr('roster').find(entry => String(entry.id) === String(id));
      const off = Boolean(row?.active);
      return confirmAction(off ? 'Switch this email off?' : 'Switch this email on?',
        off ? `${esc(row?.email || 'This email')} will not be able to sign in with a school email code until you switch it on again.` : `${esc(row?.email || 'This email')} can sign in with a school email code again.`,
        off ? 'Switch this email off.' : 'Switch this email on.',
        off ? 'Switch off' : 'Switch on',
        'Their reports stay.',
        '/api/roster/save', { action: 'toggle', id }, 'Allowed-email list updated.');
    }
    if (action === 'remove-roster') { const row = arr('roster').find(entry => String(entry.id) === String(id)); return formShell('Remove this email?', `${esc(row?.email || 'This email')} will no longer be able to sign in with a school email code. Their reports stay.`, 'roster-remove', `${lockBox('confirmed', 'Remove this email.', 'Tick the box to continue.')}`, 'Remove', { id }); }
    if (action === 'add-staff') return staffForm();
    if (action === 'edit-staff') return staffForm(arr('staff').find(person => String(person.id) === String(id)));
    if (action === 'go-activity') { state.view = 'office'; state.tab.office = 'activity'; state.officeList = 'activity'; state.query = ''; state.page = {}; render(); return; }
    if (action === 'office-tab') {
      if (id === 'records') state.tab.office = ['roster', 'people', 'activity'].includes(state.tab.office) ? state.tab.office : (state.officeList || 'roster');
      else state.tab.office = ['cleanup','maintenance'].includes(id) ? id : 'staff';
      state.query = '';
      state.page = {};
      render();
      return;
    }
    if (action === 'office-list') {
      state.tab.office = id;
      state.officeList = id;
      state.query = '';
      state.page = {};
      render();
      return;
    }
    if (action === 'open-lost') { showReport(arr('reports').find(report => String(report.id) === String(id))); return; }
    if (action === 'open-found') { showFoundReport(arr('found_reports').find(report => String(report.id) === String(id))); return; }
    if (action === 'open-item') { showItem(arr('items').find(item => String(item.id) === String(id))); return; }
    if (action === 'open-match') { openRecord('match', id); return; }
    if (action === 'open-claim') {
      if (modal.open) closeModal();
      openTask({ key: `claim:${id}`, view: 'claims', el: `claim-${id}`, id });
      return;
    }
    if (action === 'clear-quick') return clearQuick();
    if (action === 'expire') return formShell('Clean up old items?', 'Items past their keep time, with nobody checking them, will be marked Not claimed.', 'expire', `${lockBox('confirmed', 'Clean up old items now.', 'Tick the box to continue.')}${nextNote('Those items leave the active list. The activity log keeps a record.')}`, 'Clean up', {});
    if (action === 'run-matching') {
      return formShell('Find matches now?', 'This compares every open lost report with items in the office. It does not invite an owner. You still choose Approve match or Reject for each pair.',
        'run-matching', `${lockBox('confirmed', 'Find matches now.', 'Tick the box to continue.')}${nextNote('Pairs that score 60 or more show in Matches. Lower scores stay hidden.')}`, 'Find matches', {});
    }
  } catch (error) { toast(error.message, true); }
});

document.addEventListener('submit', async event => {
  const form = event.target.closest('[data-form]');
  if (!form) return;
  event.preventDefault();
  if (form.dataset.form === 'footer-start') {
    const email = String(new FormData(form).get('email') || '').trim();
    state.screen = 'auth';
    state.pending = null;
    state.authMode = 'signin';
    if (email.toLowerCase().endsWith(STUDENT_EXAMPLE)) state.signupKind = 'lpu';
    else if (email) state.signupKind = 'guest';
    render();
    window.scrollTo(0, 0);
    const input = document.querySelector('.auth-card input[name="email"]');
    if (input && email) input.value = email;
    input?.focus();
    return;
  }
  const steps = [...form.querySelectorAll('.wizard-step')];
  if (steps.length) {
    const current = steps.findIndex(step => !step.hidden);
    if (current !== steps.length - 1) { moveWizard(form.querySelector('[data-wizard="next"]')); return; }
    if (!stepValid(steps[current])) return;
    form.querySelectorAll('.wizard-step[hidden] [required]').forEach(input => { input.required = false; });
  }
  if (state.authBusy || form.dataset.submitting === 'true') return;
  prepareFormAccessibility(form);
  clearFieldErrors(form);
  document.querySelectorAll('[data-auth-error]').forEach(box => { box.hidden = true; });
  const checked = Object.fromEntries(new FormData(form).entries());
  const early = form.dataset.form === 'register'
    ? (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(checked.email || '').trim()) ? {} : { email: 'Enter a valid email address, like you@example.com.' })
    : form.dataset.form === 'school-password' || form.dataset.form === 'guest-details' ? checkSchoolPassword({ ...checked, email: state.pending?.email || checked.email })
    : form.dataset.form === 'staff' && checked.password ? Object.fromEntries([['password', pwProblem(checked.password, checked.name, checked.email, PW_MIN)], ['confirm', checked.confirm === checked.password ? '' : 'The two passwords are not the same.']].filter(([, text]) => text))
    : form.dataset.form === 'set-password' ? Object.fromEntries([['current_password', checked.current_password ? '' : 'Enter your current password.'], ['password', pwProblem(checked.password, state.user?.name, state.user?.email, PW_MIN)], ['confirm', checked.confirm === checked.password ? '' : 'The two passwords are not the same.']].filter(([, text]) => text))
    : form.dataset.form === 'set-person-password' ? Object.fromEntries([['password', pwProblem(checked.password, checked.name, checked.email, PW_MIN)], ['confirm', checked.confirm === checked.password ? '' : 'The two passwords are not the same.']].filter(([, text]) => text))
    : form.dataset.form === 'reset-password' ? Object.fromEntries([['password', pwProblem(checked.password, '', state.pending?.email || checked.email, PW_MIN)], ['confirm', checked.confirm === checked.password ? '' : 'The two passwords are not the same.']].filter(([, text]) => text))
    : {};
  form.querySelectorAll('input[name=date_lost], input[name=date_found]').forEach(input => {
    const problem = dateProblem(input.value);
    if (problem) early[input.name] = problem;
  });
  if (Object.keys(early).length) { window.LyFindReports?.edit(form); showFieldErrors(form, early); return; }
  if (window.LyFindReports?.review(form)) return;
  form.dataset.submitting = 'true';
  const submit = form.querySelector('button[type=submit]');
  const errorBox = form.querySelector('.form-error');
  if (errorBox) errorBox.hidden = true;
  const body = new FormData(form);
  const data = readPlace(Object.fromEntries(body.entries()));
  let context = {};
  try { context = JSON.parse(form.dataset.context || '{}'); } catch { context = {}; }
  const kind = form.dataset.form;
  const auth = ['setup-admin','guest-code','login', 'register', 'school-request', 'school-code', 'school-password', 'register-code', 'guest-details', 'reset-request', 'reset-code', 'reset-password'].includes(kind);
  const oldLabel = submit?.textContent;
  if (submit) {
    submit.style.minWidth = Math.ceil(submit.getBoundingClientRect().width) + 'px';
    submit.disabled = true;
    submit.setAttribute('aria-busy', 'true');
    if (auth) submit.textContent = 'Please wait…';
  }
  if (auth) setAuthBusy(true);
  let message = 'Saved.';
  let tone = 'ok';
  let closure = null;
  try {
    if (auth) {
      let result;
      if(kind==='setup-admin'){
        result=await api('/api/auth/setup-admin',{...data,setup_key:launchSetupKey});
        launchSetupKey='';
      } else if (kind === 'login') result = await api('/api/auth/login', { email: data.email, password: data.password });
      else if (kind === 'reset-request') {
        const reply = await api('/api/auth/reset/request', { email: data.email });
        state.pending = { kind: 'reset', email: reply.email, demo_code: reply.demo_code, until: Date.now() + (reply.resend_in || 60) * 1000 };
        state.authMode = 'code';
        render();
        toast('We sent a 6-digit reset code to your email.', 'wait');
        return;
      } else if (kind === 'reset-code') {
        const reply = await api('/api/auth/reset/verify', { email: state.pending?.email, code: data.code });
        state.pending = { kind: 'reset-pass', email: reply.email, setup_token: reply.setup_token };
        state.authMode = 'reset-password';
        render();
        return;
      } else if (kind === 'reset-password') {
        result = await api('/api/auth/reset/password', { email: state.pending?.email, setup_token: state.pending?.setup_token, password: data.password, confirm: data.confirm });
      }
      else if (kind === 'school-code') {
        const reply = await api('/api/auth/school/verify', { email: state.pending?.email, code: data.code });
        state.pending = { kind: 'school-pass', email: reply.email, setup_token: reply.setup_token, name: reply.name || '' };
        state.authMode = 'school-password';
        render();
        return;
      } else if (kind === 'school-password') {
        result = await api('/api/auth/school/password', { email: state.pending?.email, setup_token: state.pending?.setup_token, first_name: data.first_name, middle_name: data.middle_name || '', last_name: data.last_name, suffix: data.suffix || '', phone: data.phone || '', password: data.password, confirm: data.confirm });
      }
      else if (kind === 'guest-code') {
        result = await api('/api/auth/guest/verify', {email:state.pending?.email, code:data.code, remember_browser:body.has('remember_browser')});
      }
      else if (kind === 'register-code') {
        const reply = await api('/api/auth/register/verify', { email: state.pending?.email, code: data.code });
        state.pending = { kind: 'signup', email: reply.email, setup_token: reply.setup_token, until: state.pending?.until || 0 };
        state.authMode = 'guest-details';
        render();
        return;
      }       else if (kind === 'guest-details') {
        result = await api('/api/auth/register/finish', { email: state.pending?.email, setup_token: state.pending?.setup_token, first_name: data.first_name, middle_name: data.middle_name || '', last_name: data.last_name, suffix: data.suffix || '', phone: data.phone || '', password: data.password, confirm: data.confirm });
        state.deskSaved = result.desk_saved || 0;
      }
      else {
        const reply = kind === 'school-request'
          ? await api('/api/auth/school/request', { email: data.email })
          : await api('/api/auth/guest/request', { email: data.email });
        state.pending = { kind: kind === 'school-request' ? 'school' : 'signup', email: reply.email, demo_code:reply.demo_code, until: Date.now() + (reply.resend_in || 60) * 1000 };
        state.authMode = 'code';
        render();
        toast(kind === 'school-request' ? 'We sent a 6-digit code to your Outlook inbox.' : 'We sent a 6-digit code to your email.', 'wait');
        return;
      }
      state.user = result.user || result;
      state.csrf = result.csrf_token || state.csrf;
      state.pending = null;
      state.view = admin() ? 'today' : 'home';
      await load();
      window.scrollTo(0, 0);
      toast(kind === 'guest-details' || kind === 'school-password'
        ? `Welcome to LyFind, ${firstName(state.user.name)}.${state.deskSaved ? ' CSA already saved a lost report for you.' : ''}`
        : kind === 'reset-password'
          ? 'Password updated. You are now signed in.'
          : `Signed in as ${state.user.name}.`);
      state.deskSaved = 0;
      return;
    }
    if (kind === 'logout' || kind === 'switch-account') {
      closeModal();
      await api('/api/logout', {});
      resetSession();
      if (kind === 'switch-account') {
        state.screen = 'auth';
        state.authMode = 'signin';
      }
      await boot();
      window.scrollTo(0, 0);
      toast(kind === 'switch-account' ? 'Signed out. Sign in with the other email.' : 'You signed out.');
      return;
    }
    if (kind === 'run-matching') {
      const result = await api('/api/matching/run', {});
      state.view = 'matches';
      state.tab.matches = 'review';
      state.quick = null;
      message = result.count
        ? `Matching finished. ${result.count} suggestion${result.count === 1 ? '' : 's'} to review in Matches.`
        : 'Matching finished. Nothing scored high enough. Reports stay open.';
      tone = result.count ? 'wait' : 'ok';
    } else if (kind === 'confirm-action') {
      await api(context.path, context.payload || {});
      message = context.message || 'Saved.';
    } else if (kind === 'lost' || kind === 'guest-lost') {
      const photo_id = await window.LyFindReports.photo(form,body.get('photo_id'),upload);
      delete data.photo_id;
      delete data.guest_email;
      if (kind === 'guest-lost') {
        const held = await api('/api/reports/lost-for-guest', { ...data, guest_email: checked.guest_email, photo_id });
        if (held && held.status === 'waiting') { watchDeskHold(held); return; }
      } else await api('/api/reports/lost', { ...data, photo_id, submission_key:window.LyFindReports.key(form) });
      window.LyFindReports.complete(form);
      message = kind === 'guest-lost'
        ? 'Saved for that guest. They can see it when they sign in.'
        : 'Lost report saved. CSA will look for a match. You will see updates in My reports.';
    } else if (kind === 'found') {
      const photo_id = await window.LyFindReports.photo(form,body.get('photo_id'),upload);
      delete data.photo_id;
      await api('/api/reports/found', { ...data, photo_id, submission_key:window.LyFindReports.key(form) });
      window.LyFindReports.complete(form);
      message = data.where_now === 'security' ? 'Found report saved. CSA will collect the item from campus security.'
        : data.where_now === 'left' ? 'Found report saved. Thank you. CSA will check the place you named.'
        : 'Found report saved. Next: bring the item to the CSA office.';
      tone = data.where_now === 'security' || data.where_now === 'left' ? 'ok' : 'wait';
    } else if (kind === 'receive') {
      const photo_id = await upload(body.get('photo_id'), 'item_photo');
      delete data.photo_id;
      await api('/api/items/receive', { ...data, photo_id, board_published:body.has('board_published') });
      message = 'Item saved. Matching ran right away. Next: open Matches.';
    } else if (kind === 'claim') {
      await api('/api/claims/submit', { ...context, answers: { details: data.details }, consent: true });
      message = 'Answers sent. CSA will review them. You will see an update here.';
      tone = 'wait';
    } else if (kind === 'decision') {
      await api(`/api/claims/${context.stage}`, { claim_id: context.claim_id, passed: context.passed, reason: data.reason || '' });
      message = !context.passed ? 'Rejected. The owner can read your reason.' : context.stage === 'online' ? 'Online check passed. The owner was told to bring their ID. Next: press Start office check when they arrive.' : 'Office check passed. Next: add the three photos and press Approve handover.';
      tone = context.passed ? 'wait' : 'error';
    } else if (kind === 'consent') {
      await api('/api/claims/consent', { claim_id: context.claim_id, in_person: true, purpose: data.purpose });
      message = 'Office check started. Next: check the ID and answers, then Approve or Reject.';
      tone = 'wait';
    } else if (kind === 'approve') {
      for (const key of ['claimant_photo', 'id_photo', 'signature']) validateImage(body.get(key), true);
      const evidence = {};
      for (const key of ['claimant_photo', 'id_photo', 'signature']) evidence[key] = await upload(body.get(key), key, context.claim_id);
      await api('/api/claims/approve', { ...context, ...evidence, handover_note: data.handover_note || '' });
      message = 'Handover approved. The owner can pick up the item. Next: press Hand over item when they are here.';
      tone = 'wait';
    } else if (kind === 'release') {
      closure = arr('claims').find(claim => String(claim.id) === String(context.claim_id));
      await api('/api/claims/release', context);
    } else if (kind === 'match-decision') {
      await api('/api/matches/decide', context);
      message = context.confirmed ? 'Approved. The owner was told. Next: their answers will show in Claims.' : 'Rejected. The owner was not told.';
      tone = context.confirmed ? 'wait' : 'error';
    } else if (kind === 'expire') {
      const cleaned = await api('/api/items/expire', {});
      message = cleaned.expired ? `${cleaned.expired} old item${cleaned.expired === 1 ? '' : 's'} marked Not claimed.` : 'Nothing was old enough to clean up.';
    } else if (kind === 'review') {
      await api('/api/reports/review', { ...context, reason: data.reason || '' });
      message = 'Hidden. The record is kept, and the owner and matching no longer see it.';
    } else if (kind === 'block') {
      await api('/api/users/block', { ...context, reason: data.reason || '' });
      message = 'Account blocked. That person is signed out.';
    } else if (kind === 'roster-add') {
      await api('/api/roster/save', { action: 'add', email: data.email, name: data.name || '', student_number: data.student_number || '', role: data.role || 'student' });
      message = 'Email added to the allowed list.';
    } else if (kind === 'roster-import') {
      const file = body.get('csv');
      if (!file || !file.size) throw new Error('Choose a CSV file first.');
      const csv=await file.text();
      const preview=await api('/api/roster/preview',{csv});
      rosterDraft={csv,preview:preview.preview};
      formShell('Review allowed emails','Check the names, addresses, roles, and proposed changes before importing.','roster-commit',
        `<div class="table-wrap" tabindex="0"><table><thead><tr><th>Line</th><th>Email</th><th>Name</th><th>Role</th><th>Change</th></tr></thead><tbody>
        ${preview.rows.map(row=>`<tr><td>${row.line}</td><td>${esc(row.email)}</td><td>${esc(row.name)}</td><td>${esc(row.role)}</td><td>${esc(row.issue||row.status)}</td></tr>`).join('')}</tbody></table></div>
        ${preview.invalid?'<p class="form-error">Fix the invalid rows and choose the updated CSV.</p>':''}`,'Import reviewed accounts');
      modal.querySelector('button[type=submit]').disabled=!!preview.invalid;
      return;
    } else if (kind === 'roster-remove') {
      await api('/api/roster/save', { action: 'remove', id: context.id });
      message = 'Removed from the allowed list.';
    } else if (kind === 'set-password') {
      await api('/api/account/password', { current_password: data.current_password, password: data.password, confirm: data.confirm });
      state.flash = { view: 'account', text: 'Password updated. Use it the next time you sign in.' };
      message = 'Password updated.';
    } else if (kind === 'set-person-password') {
      await api('/api/users/password', { user_id: context.user_id, password: data.password, confirm: data.confirm });
      message = 'Password set. Tell them once. It will not be shown again.';
    } else if (kind === 'account') {
      const result = await api('/api/account/save', {
        first_name: data.first_name, middle_name: data.middle_name || '', last_name: data.last_name,
        suffix: data.suffix || '', phone: data.phone || '', student_number: data.student_number || ''});
      state.user = { ...state.user, ...result.user };
      state.flash = { view: 'account', text: 'Saved. Your name, phone, and ID number are up to date. CSA will use these details when you pick up an item.' };
      message = 'Saved. Your account details were updated.';
    } else if (kind === 'staff') {
      delete data.confirm;
      await api('/api/staff/save', { ...context, ...data, active: data.active !== undefined ? data.active === 'true' : true, role: 'admin' });
      message = 'Staff account saved.';
    }
    closeModal();
    try { await load(); } catch { savedRefreshNotice(); return; }
    if (closure) showDone(closure);
    else toast(message, tone);
  } catch (error) {
    if (kind === 'register' && /wait \d+ seconds/i.test(error.message || '')) {
      state.signupKind = 'guest';
      state.pending = { kind: 'signup', email: String(checked.email || '').trim(), until: Date.now() + 60000 };
      state.authMode = 'code';
      render();
      toast('A code is already on its way to that email. Enter it here.', 'wait');
      return;
    }
    const reportError = window.LyFindReports?.failed(form,error);
    if (error.fields) window.LyFindReports?.edit(form);
    if (error.fields && showFieldErrors(form, error.fields)) {
      // The message sits under the field it belongs to.
    } else if (errorBox) {
      errorBox.hidden = false;
      errorBox.innerHTML = statusMarkup(reportError || `That did not save. ${error.message}`, 'error');
    } else if (auth) showLoginError(error.message);
    else toast(error.message, true);
  } finally {
    if (auth) setAuthBusy(false);
    if (submit?.isConnected) {
      submit.disabled = Boolean(form.querySelector('[data-lock]:not(:checked)'));
      submit.removeAttribute('aria-busy');
      submit.style.minWidth = '';
      if (oldLabel) submit.textContent = form.dataset.reportRetry==='true'?'Try again':form.dataset.reportStage==='edit'?'Review report':oldLabel;
    }
    delete form.dataset.submitting;
  }
});

document.addEventListener('keydown', event => {
  const tab = event.target.closest?.('[role="tab"]');
  if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const all = [...tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]')];
  const at = all.indexOf(tab);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? all.length - 1 : (at + (event.key === 'ArrowRight' ? 1 : -1) + all.length) % all.length;
  event.preventDefault();
  state.keepTabFocus = true;
  all[next].click();
});
document.addEventListener('input', event => {
  if (event.target.id === 'help-search') { filterHelp(event.target.value); return; }
  const slot = event.target.closest?.('.field')?.querySelector('.field-error');
  if (slot && !slot.hidden) { slot.hidden = true; event.target.removeAttribute('aria-invalid'); restoreFieldDescription(event.target); }
  const helper = event.target.closest?.('[data-pw-set]') || (['name', 'email'].includes(event.target.name) ? event.target.closest('form')?.querySelector('[data-pw-set]') : null);
  if (helper) updatePasswordHelper(helper);
  if (!event.target.classList.contains('search-input')) return;
  const fromSide = event.target.classList.contains('side-search-input');
  const value = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = value;
    state.page = {};
    const still = event.target.isConnected ? event.target : null;
    if (fromSide && admin()) state.view = 'today';
    else if (fromSide && state.user && !document.querySelector('.toolbar .search-input')) state.view = 'reports';
    render();
    const box = still?.isConnected ? still : document.querySelector(fromSide ? '.side-search-input' : '.toolbar .search-input');
    if (box && document.activeElement !== box) {
      box.focus();
      const end = box.value.length;
      try { box.setSelectionRange(end, end); } catch (err) { /* some fields cannot place a caret */ }
    }
  }, 160);
});
document.addEventListener('focusin', event => {
  const box = event.target.closest?.('.auth-box, .auth-panel > .auth-card');
  if (!box || !event.target.matches('input, textarea, select')) return;
  setTimeout(() => {
    if (!event.target.isConnected) return;
    const field = event.target.getBoundingClientRect();
    const frame = box.getBoundingClientRect();
    if (field.top < frame.top + 8 || field.bottom > frame.bottom - 8) event.target.scrollIntoView({ block: 'nearest' });
  }, 280);
});
document.addEventListener('change', event => {
  const target = event.target;
  if (target.id === 'item-filter') { state.filter = target.value; state.quick = null; state.page.items = 1; render(); return; }
  if (target.getAttribute('data-list-filter') === 'category') { state.category = target.value; state.page = {}; render(); return; }
  if (target.name === 'place') {
    const extra = target.closest('form')?.querySelector('.place-other');
    const input = extra?.querySelector('input');
    const other = target.value === 'Other';
    if (extra) extra.hidden = !other;
    if (input) { input.required = other; input.disabled = !other; if (other) input.focus(); }
  }
  if (target.name === 'category') {
    const tip = CATEGORY_TIPS[target.value] || CATEGORY_TIPS.other;
    const form = target.closest('form');
    const desc = form?.querySelector('textarea[name=description]');
    const marks = form?.querySelector('textarea[name=identifying_marks]');
    if (desc) desc.placeholder = `For example: ${tip[0]}.`;
    if (marks) marks.placeholder = tip[1];
  }
  if (target.name === 'where_now') {
    const form = target.closest('form');
    const turn = form?.querySelector('.turn-in');
    const input = turn?.querySelector('input');
    const note = form?.querySelector('[data-where-note]');
    const holding = target.value === 'with_me';
    if (turn) turn.hidden = !holding;
    if (input) { input.disabled = !holding; input.required = holding; }
    if (note) note.textContent = {
      with_me: 'Bring it to the CSA office by that day. Nobody can claim it before it arrives.',
      security: 'CSA will collect it from campus security. Say which gate or office in the place above.',
      left: 'Name the exact spot in the place above. Staff may collect it, but valuables can disappear, so bring it in if you can.'
    }[target.value] || '';
  }
  if (target.name === 'date_lost' || target.name === 'date_found') {
    const problem = dateProblem(target.value);
    const slot = target.form?.querySelector(`[data-error-for="${target.name}"]`);
    if (slot) { slot.hidden = !problem; slot.textContent = problem; }
    if (problem) target.setAttribute('aria-invalid', 'true');
    else target.removeAttribute('aria-invalid');
  }
  if (target.name === 'date_found') {
    const turn = target.form?.querySelector('[name=turn_in_deadline]');
    if (turn) turn.min = target.value;
  }
  if (target.matches('[data-brand-choice]')) {
    const region = target.closest('.brand-field');
    const wrap = region.querySelector('.brand-name');
    const input = wrap.querySelector('input');
    const known = target.value === 'known';
    wrap.hidden = !known;
    input.disabled = !known;
    input.required = known;
    const caption = wrap.querySelector('span');
    if (caption) caption.textContent = known ? 'Brand name' : 'Brand name (optional)';
    if (known) input.focus();
  }
  if (target.matches('[data-lock]')) {
    const submit = target.form.querySelector('button[type=submit]');
    const why = target.form.querySelector('.submit-why');
    if (submit) { submit.disabled = !target.checked; submit.title = target.checked ? '' : target.dataset.lock; }
    if (why) why.hidden = target.checked;
  }
  if (target.matches('input[type=file][accept^="image/"]')) previewFile(target);
});
modal.addEventListener('cancel', event => { if (modal.querySelector('form[data-submitting="true"]')) event.preventDefault(); });
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (document.querySelector('dialog[open]')) return;
  const open = document.querySelector('details.more[open]');
  if (open && !modal.open) { open.open = false; open.querySelector('summary')?.focus(); return; }
  if (document.querySelector('.sidebar.open, .pub-drawer.open')) { event.preventDefault(); closeMenu(); }
});

// Phones show each table row as a card; every cell needs its column name to stay readable.
function labelTables(root) {
  root.querySelectorAll('table').forEach(table => {
    const heads = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim());
    table.querySelectorAll('tbody tr').forEach(row => {
      [...row.children].forEach((cell, index) => { if (heads[index]) cell.dataset.label = heads[index]; });
    });
  });
}
function syncDeskDots() {
  const rail = document.querySelector('.desk-steps');
  const dots = document.querySelector('.desk-dots');
  if (!rail || !dots) return;
  const overflow = rail.scrollWidth > rail.clientWidth + 4;
  dots.hidden = !overflow;
  const marks = [...dots.children];
  if (!overflow) { marks.forEach(dot => dot.classList.remove('on')); return; }
  const max = rail.scrollWidth - rail.clientWidth;
  const index = Math.max(0, Math.min(marks.length - 1, Math.round((rail.scrollLeft / max) * (marks.length - 1))));
  marks.forEach((dot, i) => dot.classList.toggle('on', i === index));
}
function syncSlideDots() {
  document.querySelectorAll('.how-grid, .who-grid, .contact-grid, .help-rail, .found-grid, .footer-links, .tabs, .table-wrap, .tracker:not(.help-tracker)').forEach(rail => {
    if (rail.closest('.guide, .auth')) return;
    let dots = rail.nextElementSibling;
    if (!dots || !dots.classList.contains('slide-dots')) {
      dots = document.createElement('div');
      dots.className = 'slide-dots';
      dots.hidden = true;
      dots.setAttribute('aria-hidden', 'true');
      rail.after(dots);
    }
    const items = [...rail.children];
    const table = rail.classList.contains('table-wrap');
    const overflow = rail.scrollWidth > rail.clientWidth + 8;
    if (!table) rail.classList.toggle('can-slide', overflow);
    const count = table
      ? Math.min(6, Math.max(2, Math.ceil(rail.scrollWidth / Math.max(rail.clientWidth, 1))))
      : Math.min(items.length, 8);
    if (!overflow || (!table && items.length < 2)) { dots.hidden = true; return; }
    if (dots.childElementCount !== count) dots.replaceChildren(...Array.from({ length: count }, () => document.createElement('i')));
    dots.hidden = false;
    const max = rail.scrollWidth - rail.clientWidth;
    const index = Math.max(0, Math.min(count - 1, Math.round((rail.scrollLeft / Math.max(max, 1)) * (count - 1))));
    [...dots.children].forEach((dot, i) => dot.classList.toggle('on', i === index));
    if (!rail.dataset.slideDots) {
      rail.dataset.slideDots = '1';
      rail.addEventListener('scroll', syncSlideDots, { passive: true });
    }
  });
}
function finishRender() {
  syncQuickTools();
  prepareFormAccessibility(document);
  syncSidebar();
  labelTables(document);
  const rail = document.querySelector('.desk-steps');
  if (rail && !rail.dataset.dots) {
    rail.dataset.dots = '1';
    rail.addEventListener('scroll', syncDeskDots, { passive: true });
  }
  syncDeskDots();
  syncSlideDots();
  if (state.focusId) {
    const card = document.getElementById(state.focusId);
    card?.scrollIntoView({ block: 'center', inline: 'nearest' });
    card?.querySelector('.btn.primary')?.focus({ preventScroll: true });
    state.focusId = null;
  }
  const pinRowStart = () => {
    document.querySelectorAll('.tracker:not(.help-tracker)').forEach(rail => { rail.scrollLeft = 0; });
  };
  pinRowStart();
  requestAnimationFrame(pinRowStart);
}
window.addEventListener('resize', () => { syncDeskDots(); syncSlideDots(); });
function drawer() {
  return document.querySelector('.sidebar') || document.querySelector('.pub-drawer');
}
function isLargeText() {
  return document.documentElement.dataset.textSize === 'large';
}
function syncSidebar() {
  const sidebar = drawer();
  if (!sidebar) return;
  const open = sidebar.classList.contains('open');
  const typing = sidebar.contains(document.activeElement);
  const collapsed = sidebar.classList.contains('sidebar')
    ? (appDrawerLayout.matches || isLargeText())
    : mobileLayout.matches;
  sidebar.inert = collapsed && !open && !typing;
}
function toggleMenu() {
  const sidebar = drawer();
  if (!sidebar) return;
  if (sidebar.classList.contains('open')) { closeMenu(); return; }
  sidebar.classList.add('open');
  sidebar.inert = false;
  const overlay = document.querySelector('.nav-overlay');
  if (overlay) overlay.hidden = false;
  document.querySelector('.menu-button')?.setAttribute('aria-expanded', 'true');
  sidebar.querySelector('.nav-item')?.focus();
}
function closeMenu(restore) {
  const sidebar = drawer();
  if (!sidebar) return;
  const wasOpen = sidebar.classList.contains('open');
  sidebar.classList.remove('open');
  document.querySelector('.menu-button')?.setAttribute('aria-expanded', 'false');
  const overlay = document.querySelector('.nav-overlay');
  if (overlay) overlay.hidden = true;
  if (restore !== false && wasOpen) document.querySelector('.menu-button')?.focus();
  if (sidebar.contains(document.activeElement)) document.activeElement?.blur?.();
  syncSidebar();
}
mobileLayout.addEventListener('change', () => closeMenu(false));
appDrawerLayout.addEventListener('change', () => closeMenu(false));
new MutationObserver(() => {
  const sidebar = drawer();
  if (!sidebar) return;
  const collapsed = sidebar.classList.contains('sidebar')
    ? (appDrawerLayout.matches || isLargeText())
    : mobileLayout.matches;
  if (!collapsed) closeMenu(false);
  else syncSidebar();
}).observe(document.documentElement, { attributes: true, attributeFilter: ['data-text-size'] });

new MutationObserver(syncDialogTheme).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['open'] });
window.addEventListener('storage', event => {
  if (event.key === THEME_KEY) applyTheme(event.newValue);
});
boot();

function renderFoundBoard(){
 const rows=arr('found_board');
 return pageHead('Found items','General listings of items received by CSA. Report what you lost so staff can check ownership.')+
   (rows.length?`<div class="cards">${rows.map(row=>`<article class="card"><h2>${esc(String(row.category).replaceAll("_"," "))}</h2><p>Campus · Week of ${esc(row.week)}</p></article>`).join('')}</div>`:empty('No listings yet','CSA can publish general listings after physical receipt.','inventory'));
}
function renderMaintenance(){
 return pageHead('Workspace maintenance','Save a recovery copy, clear demo storage, or restore classroom samples.')+officeOuter('maintenance')+
   `<section class="card"><h2>Back up workspace</h2><p>Saves records and uploaded images together on the host computer.</p>${button('Create backup','workspace-backup','','primary')}</section>
   ${state.data.can_reset_demo?`<section class="card"><h2>Start fresh (0 reports)</h2><p>Backs up this demo, clears all reports, items, matches, claims, and uploads to zero, and keeps demo accounts ready.</p>${button('Clear all reports','workspace-clear','','secondary')}</section>
   <section class="card"><h2>Reset demo with samples</h2><p>Backs up this demo, restores fictional sample records, and signs out demo users.</p>${button('Reset demo','workspace-reset','','secondary')}</section>`:''}`;
}
document.addEventListener('change',event=>{
 if(event.target.name!=='photo_id')return;
 const row=event.target.closest('form')?.querySelector('[data-ai-fill-row]');
 if(row)row.hidden=!event.target.files?.length;
});
document.addEventListener('input',event=>{
 if(event.target.name!=='code')return;
 const form=event.target.form, box=form?.querySelector('[data-remember-guest]');
 if(!box)return;
 const ready=/^[0-9]{6}$/.test(event.target.value);
 box.hidden=!ready;box.querySelector('input').disabled=!ready;
});
document.addEventListener('click',async event=>{
 const control=event.target.closest('[data-action]');
 if(!control)return;
 try{
  if(control.dataset.action==='workspace-backup'){
   control.disabled=true;
   const result=await api('/api/maintenance/backup',{});
   formShell('Backup saved','Open the LyFind folder on the host computer, then data → backups.','backup-close',`<p>${esc(result.backup)}</p>`,'Done');
  }
  if(control.dataset.action==='workspace-clear'){
   formShell('Start fresh with 0 reports?','A backup is saved first. This clears all demo reports, items, matches, claims, and uploads while keeping demo accounts.','workspace-clear',
     '<label class="check-field"><input name="confirmed" type="checkbox" required><span>I understand all demo reports and uploads will be cleared.</span></label>','Back up and clear');
  }
  if(control.dataset.action==='workspace-reset'){
   formShell('Reset the demo?','A backup is saved first. This restores samples and signs out demo users.','workspace-reset',
     '<label class="check-field"><input name="confirmed" type="checkbox" required><span>I understand the demo records will be replaced.</span></label>','Back up and reset');
  }
  if(control.dataset.action==='claim-pass'){
   const claim=arr('claims').find(row=>String(row.id)===String(control.dataset.id));
   if(!claim){toast('That claim could not be found.',true);return;}
   const released=claim.status==='released';
   const ref='LYF-CLM-'+String(claim.id).padStart(4,'0');
   const owner=claim.claimant_name||state.user?.name||'Verified owner';
   const idNo=claim.claimant_student_number||state.user?.student_number||'';
   const stage=released?'Handed back to owner':claim.status==='approved'?'Approved for pickup':claim.status==='verified'?'Verified, awaiting approval':'Bring valid ID for in-person check';
   const when=claim.released_at?dateText(claim.released_at):claim.consent_at?dateText(claim.consent_at):today();
   openModal(`<div class="modal-head"><div><h2 id="modal-title">${released?'Handover receipt':'Digital Claim Pass'}</h2><p>${released?'Official record of item return from LPU Cavite CSA.':'Show this pass and a valid ID at the CSA desk.'}</p></div><button class="icon-button" type="button" data-action="close-modal" aria-label="Close" title="Close">${svg('close')}</button></div>
    <div class="modal-body"><div class="claim-pass-card">
     <div class="claim-pass-top"><span class="kicker">LPU CAVITE · CSA LOST AND FOUND</span><strong class="claim-pass-ref">${esc(ref)}</strong></div>
     <h3 class="claim-pass-title">${esc(claimTitle(claim))}</h3>
     <dl class="claim-pass-grid">
      <div><dt>Category</dt><dd>${esc(catName(claim.item_category))}</dd></div>
      <div><dt>Status</dt><dd>${esc(stage)}</dd></div>
      <div><dt>Owner</dt><dd>${esc(owner)}${idNo?` (${esc(idNo)})`:''}</dd></div>
      <div><dt>${released?'Returned on':'Updated'}</dt><dd>${esc(when)}</dd></div>
      <div><dt>Office location</dt><dd>${esc(OFFICE.name)}, ${esc(OFFICE.place)}</dd></div>
      <div><dt>Office hours</dt><dd>${esc(OFFICE.hours)}</dd></div>
     </dl>
     <p class="claim-pass-foot">${released?'Verified and released by Center for Student Affairs staff.':'Valid school or government ID is required before CSA releases any item.'}</p>
    </div></div>
    <div class="modal-actions"><button class="btn" type="button" data-action="close-modal">Close</button><button class="btn primary" type="button" data-action="print-pass">Print / Save PDF</button></div>`);
  }
  if(control.dataset.action==='hero-slide'){
   setHeroSlide(Number(control.dataset.slide)||0);
   startHeroSlideshow();
   setHeroSlide(Number(control.dataset.slide)||0);
  }
  if(control.dataset.action==='print-pass'){
   window.print();
  }
  if(control.dataset.action==='toggle-board'){
   await api('/api/items/board',{item_id:Number(control.dataset.id),published:control.dataset.published==='true'});
   closeModal();await load();toast('Found-items listing updated.');
  }
  if(control.dataset.action==='ai-fill-photo'){
   const form=control.closest('form');
   const input=form?.querySelector('input[name="photo_id"]');
   const file=input?.files?.[0];
   if(!file||!file.size){toast('Choose a photo first.',true);input?.focus();return;}
   validateImage(file,true);
   const label=control.querySelector('span');
   const prev=label?label.textContent:'Fill details with AI';
   control.disabled=true;
   if(label)label.textContent='Reading photo...';
   try{
    const content=await new Promise((resolve,reject)=>{
     const reader=new FileReader();
     reader.onload=()=>resolve(String(reader.result).split(',')[1]);
     reader.onerror=()=>reject(new Error('This image could not be read.'));
     reader.readAsDataURL(file);
    });
    const info=await api('/api/ai/describe-photo',{content});
    const cat=form.querySelector('select[name="category"]');
    if(cat&&info.category){cat.value=info.category;cat.dispatchEvent(new Event('change',{bubbles:true}));}
    const col=form.querySelector('select[name="color"]');
    if(col&&info.color){col.value=info.color;col.dispatchEvent(new Event('change',{bubbles:true}));}
    const bc=form.querySelector('select[name="brand_choice"]');
    const bn=form.querySelector('input[name="brand"]');
    if(bc&&info.brand){
     bc.value='known';bc.dispatchEvent(new Event('change',{bubbles:true}));
     if(bn){bn.disabled=false;bn.value=info.brand;bn.dispatchEvent(new Event('input',{bubbles:true}));}
    }
    const desc=form.querySelector('textarea[name="description"]');
    if(desc&&info.description){desc.value=info.description;desc.dispatchEvent(new Event('input',{bubbles:true}));}
    toast('Details filled from photo. Check and edit anything before submitting.');
   }finally{
    if(label)label.textContent=prev;
   }
  }
 }catch(error){toast(error.message,true)}finally{control.disabled=false}
});

document.addEventListener('submit',async event=>{
 const form=event.target;
 if(!['workspace-reset','workspace-clear','backup-close'].includes(form.dataset.form))return;
 event.preventDefault();event.stopImmediatePropagation();
 if(form.dataset.submitting)return;
 if(form.dataset.form==='backup-close'){closeModal();return;}
 const submit=form.querySelector('button[type=submit]');
 form.dataset.submitting='true';submit.disabled=true;
 const isClear=form.dataset.form==='workspace-clear';
 try{
  const result=await api(isClear?'/api/maintenance/clear-demo':'/api/maintenance/reset-demo',{confirmed:new FormData(form).has('confirmed')});
  window.LyFindReports?.clearTesting();
  closeModal();resetSession();await boot();
  toast((isClear?'Demo cleared to 0 reports.':'Demo restored.')+' Backup saved in data / backups as '+result.backup);
 }catch(error){toast(error.message,true)}finally{delete form.dataset.submitting;submit.disabled=false}
},true);

document.addEventListener('submit',async event=>{
 const form=event.target;
 if(form.dataset.form!=='roster-commit')return;
 event.preventDefault();event.stopImmediatePropagation();
 if(form.dataset.submitting||!rosterDraft)return;
 form.dataset.submitting='true';
 const submit=form.querySelector('button[type=submit]');submit.disabled=true;
 try{
  const result=await api('/api/roster/import',rosterDraft);
  rosterDraft=null;closeModal();await load();toast(result.added+' school emails added or updated.');
 }catch(error){toast(error.message,true)}finally{delete form.dataset.submitting;submit.disabled=false}
},true);
