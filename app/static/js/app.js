const toast = document.getElementById('toast');
const notify = (msg) => {
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => toast.style.display = 'none', 2800);
};

document.getElementById('settings-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = new FormData(e.target);
  const res = await fetch('/settings', { method: 'POST', body });
  const data = await res.json();
  notify(data.message || 'Сохранено');
});

document.getElementById('refresh-btn')?.addEventListener('click', async () => {
  const res = await fetch('/refresh', { method: 'POST' });
  const data = await res.json();
  notify(data.message || 'Обновлено');
  setTimeout(() => window.location.reload(), 600);
});

document.querySelectorAll('.send-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const postId = btn.dataset.postId;
    const res = await fetch(`/send/${postId}`, { method: 'POST' });
    const data = await res.json();
    notify(data.message || (data.ok ? 'Отправлено' : 'Ошибка'));
  });
});

if (window.APP_CONFIG?.autoRefresh) {
  setInterval(async () => {
    await fetch('/refresh', { method: 'POST' });
    window.location.reload();
  }, 30 * 60 * 1000);
}
