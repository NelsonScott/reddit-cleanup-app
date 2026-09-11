(function () {
  var root = document.getElementById('job');
  if (!root) return;
  var url = root.dataset.statusUrl;
  var $ = function (id) { return document.getElementById(id); };
  var timer = null;
  function paint(j) {
    $('status').textContent = j.status;
    $('current').textContent = j.current ? '· ' + j.current : '';
    $('subs').textContent = j.submissions_deleted;
    $('comms').textContent = j.comments_deleted;
    $('skipped').textContent = j.skipped;
    $('errors').textContent = j.errors;
    $('dot').className = 'dot ' + j.status;
    if (j.error_message) { $('error').textContent = j.error_message; $('error').classList.remove('hidden'); }
    if (j.finished) {
      $('cancel-form').classList.add('hidden');
      document.title = (j.status === 'done' ? 'Done' : j.status) + ' · Reddit Cleaner';
      if (timer) clearInterval(timer);
    }
  }
  function poll() {
    fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(paint)
      .catch(function () { $('status').textContent = 'connection lost, retrying'; });
  }
  poll();
  timer = setInterval(poll, 1500);
})();
