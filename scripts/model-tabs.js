<script>
function switchTab(btn, id) {
  var container = btn.closest('.tab-container');
  container.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  container.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  btn.classList.add('active');
  container.querySelector('#tab-' + id).classList.add('active');
}
</script>
