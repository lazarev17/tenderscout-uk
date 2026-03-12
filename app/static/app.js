/* TenderScout UK — JavaScript */

document.addEventListener('DOMContentLoaded', () => {
    // Animate stat counters on scroll
    animateCounters();

    // Auto-submit filters on change
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        const selects = filterForm.querySelectorAll('.filter-select');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                filterForm.submit();
            });
        });
    }
});

// ─── Counter Animation ─────────────────────────────────────

function animateCounters() {
    const counters = document.querySelectorAll('.stat-value[data-count]');
    if (!counters.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const target = parseInt(el.dataset.count, 10);
                if (isNaN(target)) return;

                animateNumber(el, 0, target, 1200);
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.3 });

    counters.forEach(counter => observer.observe(counter));
}

function animateNumber(el, from, to, duration) {
    const start = performance.now();
    const diff = to - from;

    function update(time) {
        const elapsed = time - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(from + diff * eased);
        el.textContent = current.toLocaleString();
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// ─── Smooth scroll for anchor links ─────────────────────── 

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});
