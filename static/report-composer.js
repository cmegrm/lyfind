/* Report-only drafts and a review step. Never persists passwords, claim answers, or image bytes. */
(() => {
  'use strict';
  const PREFIX = 'lyfind-report-draft:v1:';
  const MAX_AGE = 7 * 86400000;
  const FIELDS = ['category','date_lost','date_found','description','color','brand_choice','brand','place','place_other','time_lost','time_found','identifying_marks','where_now','turn_in_deadline'];
  const sessions = new WeakMap();
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const token = () => [...crypto.getRandomValues(new Uint8Array(24))].map(n => n.toString(16).padStart(2,'0')).join('');
  function keyFor(user, mode, kind) { return `${PREFIX}${mode}:${user.id}:${encodeURIComponent(user.email)}:${kind}`; }
  function read(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      if (!value || !Number.isFinite(value.updated) || Date.now()-value.updated > MAX_AGE) { localStorage.removeItem(key); return null; }
      const fields = {};
      FIELDS.forEach(name => { if (typeof value.fields?.[name] === 'string') fields[name] = value.fields[name].slice(0,3000); });
      return { fields, updated: value.updated, submissionKey: /^[a-f0-9]{48}$/.test(value.submissionKey) ? value.submissionKey : token(),
        photoId: Number.isSafeInteger(value.photoId) && value.photoId > 0 ? value.photoId : null,
        photoName: typeof value.photoName === 'string' ? value.photoName.slice(0,180) : '', photoSignature: typeof value.photoSignature === 'string' ? value.photoSignature.slice(0,240) : '' };
    } catch { return null; }
  }
  function remove(key) { try { localStorage.removeItem(key); } catch { /* storage unavailable */ } }
  function status(form, message) {
    const target = form.querySelector('[data-draft-status]');
    if (target && target.textContent !== message) target.textContent = message;
  }
  function save(form) {
    const entry = sessions.get(form);
    if (!entry?.key || entry.pending || form.dataset.reportSaved) return;
    clearTimeout(entry.timer);
    const fields = {};
    for (const name of FIELDS) {
      const input = form.elements.namedItem(name);
      if (input && typeof input.value === 'string') fields[name] = input.value.slice(0,3000);
    }
    const meaningful = ['category','description','place','place_other','color','brand','identifying_marks'].some(name => fields[name]?.trim()) || entry.photoName;
    if (!meaningful) return;
    try {
      localStorage.setItem(entry.key,JSON.stringify({fields,updated:Date.now(),submissionKey:entry.submissionKey,photoId:entry.photoId,photoName:entry.photoName,photoSignature:entry.photoSignature}));
      status(form, navigator.onLine ? 'Draft saved on this browser for 7 days.' : 'Offline. Your draft is saved on this browser.');
    } catch { status(form,'Draft storage is unavailable. Your details stay in this open form.'); }
  }
  function edit(form) {
    if (!sessions.has(form)) return;
    form.querySelector('[data-report-edit]').hidden = false;
    form.querySelector('[data-report-review]').hidden = true;
    form.querySelector('[data-report-back]').hidden = true;
    form.querySelector('button[type=submit]').textContent = 'Review report';
    form.dataset.reportStage = 'edit';
    delete form.dataset.reportRetry;
    form.querySelector('input:not([type=hidden]):not([disabled]),select,textarea')?.focus();
  }
  function review(form) {
    const entry = sessions.get(form);
    if (!entry || form.dataset.reportStage === 'review') return false;
    if (entry.pending) return true;
    save(form);
    const rows = [];
    const labels = [['guest_email','Guest email'],['category','Kind of item'],['description','Description'],['date_lost','Date lost'],['date_found','Date found'],['place','Place'],['time_lost','Time'],['time_found','Time'],['color','Color'],['brand_choice','Brand'],['identifying_marks','Private identifying details'],['where_now','Where it is now'],['turn_in_deadline','Bring to CSA by']];
    labels.forEach(([name,label]) => {
      const input = form.elements.namedItem(name);
      if (!input || input.disabled || input.closest('[hidden]')) return;
      let value = input.tagName === 'SELECT' ? input.selectedOptions[0]?.textContent : input.value;
      if (name === 'place' && input.value === 'Other') value = form.elements.namedItem('place_other')?.value;
      if (name === 'brand_choice' && input.value === 'known') value = form.elements.namedItem('brand')?.value;
      if (value) rows.push(`<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`);
    });
    const file = form.elements.namedItem('photo_id')?.files?.[0];
    const photo = file?.name || (entry.photoId ? `${entry.photoName || 'Photo'} (already uploaded)` : entry.photoName ? `Not attached. Reselect ${entry.photoName} if you want to include it.` : 'No photo attached');
    rows.push(`<div><dt>Photo</dt><dd>${escape(photo)}</dd></div>`);
    const found = form.dataset.form === 'found';
    form.querySelector('[data-report-review]').innerHTML = `<h3 id="report-review-title" tabindex="-1">Review your report</h3><p>Check the details. Nothing is submitted until you confirm below.</p><dl class="report-summary">${rows.join('')}</dl><p class="note">${found ? 'The item becomes claimable only after CSA physically receives it.' : 'Only you and CSA can see this report. CSA confirms a match before inviting you to claim.'}</p>`;
    form.querySelector('[data-report-edit]').hidden = true;
    form.querySelector('[data-report-review]').hidden = false;
    form.querySelector('[data-report-back]').hidden = false;
    form.querySelector('button[type=submit]').textContent = entry.submitLabel;
    form.dataset.reportStage = 'review';
    form.querySelector('#report-review-title').focus();
    return true;
  }
  function attach(form, {user,mode}) {
    const kind = form.dataset.form;
    if (!['lost','found','guest-lost'].includes(kind) || sessions.has(form)) return;
    const key = kind !== 'guest-lost' && user ? keyFor(user,mode,kind) : null;
    const draft = key ? read(key) : null;
    const entry = {key,submissionKey:token(),photoId:null,photoName:'',photoSignature:'',submitLabel:form.querySelector('button[type=submit]').textContent,pending:Boolean(draft)};
    sessions.set(form,entry);
    const body = form.querySelector('.modal-body');
    const editor = document.createElement('div');editor.dataset.reportEdit = '';
    [...body.children].filter(el=>!el.classList.contains('form-error')).forEach(el=>editor.append(el));
    body.append(editor);
    const summary = document.createElement('section');summary.dataset.reportReview='';summary.hidden=true;body.append(summary);
    const note = document.createElement('p');note.className='draft-status';note.dataset.draftStatus='';note.setAttribute('role','status');note.setAttribute('aria-live','polite');body.prepend(note);
    const actions = form.querySelector('.modal-actions');
    const back = document.createElement('button');back.type='button';back.className='btn secondary';back.dataset.reportBack='';back.textContent='Edit details';back.hidden=true;actions.insertBefore(back,actions.querySelector('button[type=submit]'));
    back.addEventListener('click',()=>edit(form));
    form.querySelector('button[type=submit]').textContent='Review report';
    form.dataset.reportStage='edit';
    if (draft) {
      const choice=document.createElement('section');choice.className='draft-choice';choice.innerHTML=`<h3>Resume your unfinished report?</h3><p>Saved on this browser. Photos not yet uploaded must be selected again.</p><div class="banner-actions"><button type="button" class="btn primary" data-resume-draft>Resume draft</button><button type="button" class="btn secondary" data-discard-draft>Discard draft</button></div>`;
      body.prepend(choice);editor.hidden=true;form.querySelector('button[type=submit]').hidden=true;
      choice.querySelector('[data-resume-draft]').focus();
      const begin=()=>{entry.pending=false;choice.remove();editor.hidden=false;form.querySelector('button[type=submit]').hidden=false;};
      choice.querySelector('[data-resume-draft]').addEventListener('click',()=>{
        Object.assign(entry,{submissionKey:draft.submissionKey,photoId:draft.photoId,photoName:draft.photoName,photoSignature:draft.photoSignature});
        for(const name of ['category','place','brand_choice','where_now']){const input=form.elements.namedItem(name);if(input && draft.fields[name]!==undefined){input.value=draft.fields[name];input.dispatchEvent(new Event('change',{bubbles:true}));}}
        Object.entries(draft.fields).forEach(([name,value])=>{const input=form.elements.namedItem(name);if(input)input.value=value;});
        begin();status(form,entry.photoName&&!entry.photoId?`Draft resumed. Reselect ${entry.photoName} to include the photo.`:'Draft resumed. Review the details before submitting.');
        editor.querySelector('input:not([disabled]),select,textarea')?.focus();
      });
      choice.querySelector('[data-discard-draft]').addEventListener('click',()=>{remove(key);begin();status(form,'Starting a new report.');editor.querySelector('input:not([disabled]),select,textarea')?.focus();});
    } else status(form,key?'Unfinished details are saved on this browser. Photos are not stored here.':'Review the guest details before submitting.');
    const changed=event=>{
      if(event.target.type==='file'){
        const file=event.target.files?.[0];const signature=file?`${file.name}:${file.size}:${file.lastModified}`:'';
        if(signature!==entry.photoSignature){entry.photoId=null;entry.photoName=file?.name||'';entry.photoSignature=signature;}
      }
      clearTimeout(entry.timer);entry.timer=setTimeout(()=>save(form),250);
    };
    form.addEventListener('input',changed);form.addEventListener('change',changed);
  }
  window.LyFindReports = {
    attach,review,edit,flush:save,
    list(user,mode){if(!user)return[];return ['lost',...(user.role==='guest'?[]:['found'])].filter(kind=>read(keyFor(user,mode,kind))).map(kind=>({kind}));},
    key(form){return sessions.get(form)?.submissionKey;},
    async photo(form,file,upload){const entry=sessions.get(form);if(entry?.photoId)return entry.photoId;const id=await upload(file,'report_photo');if(entry){entry.photoId=id;save(form);}return id;},
    complete(form){const entry=sessions.get(form);form.dataset.reportSaved='true';if(entry){clearTimeout(entry.timer);if(entry.key)remove(entry.key);}},
    clearTesting(){try{Object.keys(localStorage).filter(key=>key.startsWith(PREFIX+'test:')).forEach(remove);}catch{}},
    failed(form,error){const entry=sessions.get(form);if(!entry)return;save(form);if(error.retryable){if(entry.key){form.dataset.reportRetry='true';return 'We could not confirm the save. Your details are kept. Try again safely, or check My reports.';}return 'We could not confirm the save. Check the guest report before trying again. Your details remain in this form.';}edit(form);return error.message;}
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden)document.querySelectorAll('form[data-report-stage]').forEach(save);});
  window.addEventListener('pagehide',()=>document.querySelectorAll('form[data-report-stage]').forEach(save));
  window.addEventListener('offline',()=>document.querySelectorAll('form[data-report-stage]').forEach(save));
})();
