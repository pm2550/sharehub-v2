(function () {
  var confirmModal = document.getElementById('confirm-delete-modal');
  var confirmBtn = document.getElementById('confirm-delete-btn');
  var confirmMessage = document.getElementById('confirm-delete-message');
  var pendingForm = null;

  // 显示确认删除模态框
  window.showDeleteConfirm = function (form, message) {
    pendingForm = form;
    if (message) {
      confirmMessage.textContent = message;
    } else {
      confirmMessage.textContent = '确定要删除这个帖子吗？';
    }
    confirmModal.classList.add('on');
    confirmModal.setAttribute('aria-hidden', 'false');
  };

  // 确认删除按钮点击
  if (confirmBtn) {
    confirmBtn.addEventListener('click', function () {
      if (pendingForm) {
        // 移除 onsubmit 事件避免再次弹窗
        pendingForm.onsubmit = null;
        pendingForm.submit();
        pendingForm = null;
      }
      confirmModal.classList.remove('on');
      confirmModal.setAttribute('aria-hidden', 'true');
    });
  }

  // 为所有带 data-confirm-delete 的表单添加确认逻辑
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-confirm-delete]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var message = form.getAttribute('data-confirm-delete');
        showDeleteConfirm(form, message);
      });
    });
  });
})();
