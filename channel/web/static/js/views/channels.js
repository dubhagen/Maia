/* Channels view. Messaging channels are removed. The web console is the
   chat surface; the local terminal stays available from the process, not here. */

function loadChannelsView() {
    const container = document.getElementById('channels-content');
    if (!container) return;
    const title = (typeof t === 'function' && t('channels_title')) || 'Web console';
    const desc = (typeof t === 'function' && t('channels_desc')) ||
        'Chat uses the web console. The local terminal is still available.';
    container.innerHTML =
        '<div class="bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-6">' +
        '<h3 class="font-semibold text-slate-800 dark:text-slate-100">' + title + '</h3>' +
        '<p class="text-sm text-slate-500 dark:text-slate-400 mt-2">' + desc + '</p>' +
        '</div>';
}
