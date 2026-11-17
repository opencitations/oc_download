/* Dump version selector of the download page.
 *
 * Each dataset section lists all its dumps; only the selected one is visible.
 * The address keeps track of the choice, so a dump can be linked directly:
 *   #meta              latest Meta dump
 *   #meta-2026-01-20   the Meta dump released on that date
 */
(function () {
    'use strict';

    var sections = Array.prototype.slice.call(document.querySelectorAll('[data-dataset]'));

    function dumpsOf(section) {
        return Array.prototype.slice.call(section.querySelectorAll('[data-dump]'));
    }

    /* Show one dump of a section; without an id, show the latest (the first). */
    function showDump(section, dumpId) {
        var dumps = dumpsOf(section);
        var target = dumps.filter(function (d) { return d.id === dumpId; })[0] || dumps[0];
        dumps.forEach(function (d) {
            d.classList.toggle('is-active', d === target);
        });
        var select = section.querySelector('[data-version-select]');
        if (select) {
            select.value = target.id;
        }
        return target === dumps[0];
    }

    function setHash(hash) {
        if (window.history && window.history.replaceState) {
            window.history.replaceState(null, '', '#' + hash);
        }
    }

    /* Open the dump (or dataset) named in the address, if any.
     * The browser cannot scroll to a dump that was hidden when the page
     * loaded, so the jump is done here once the dump is visible. */
    function applyHash() {
        var id = decodeURIComponent(window.location.hash.slice(1));
        if (!id) {
            return;
        }
        var el = document.getElementById(id);
        if (!el) {
            return;
        }
        var section = el.closest('[data-dataset]');
        if (!section) {
            return;
        }
        showDump(section, el.hasAttribute('data-dump') ? id : null);
        try {
            el.scrollIntoView({ behavior: 'instant', block: 'start' });
        } catch (e) {
            el.scrollIntoView();
        }
    }

    sections.forEach(function (section) {
        var select = section.querySelector('[data-version-select]');
        if (select) {
            select.addEventListener('change', function () {
                var isLatest = showDump(section, select.value);
                setHash(isLatest ? section.id : select.value);
            });
        }

        section.addEventListener('click', function (event) {
            var link = event.target.closest('[data-show-latest]');
            if (!link) {
                return;
            }
            event.preventDefault();
            showDump(section, null);
            setHash(section.id);
            if (select) {
                select.focus();
            }
        });
    });

    window.addEventListener('hashchange', applyHash);
    applyHash();
})();
