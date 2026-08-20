(() => {
  const form = document.getElementById("match-form");
  const tipsBtn = document.getElementById("tips-btn");
  const matchBtn = document.getElementById("match-btn");
  const output = document.getElementById("output");
  const adviceEl = document.getElementById("advice");
  const jobList = document.getElementById("job-list");
  const modeBadge = document.getElementById("mode-badge");
  const outputTitle = document.getElementById("output-title");
  const topbar = document.querySelector(".topbar");

  const profileEl = () => document.getElementById("profile");
  const searchEl = () => document.getElementById("search");
  const categoryEl = () => document.getElementById("category");

  window.addEventListener("scroll", () => {
    topbar.classList.toggle("scrolled", window.scrollY > 24);
  }, { passive: true });

  function payload() {
    return {
      profile: profileEl().value.trim(),
      search: searchEl().value.trim(),
      category: categoryEl().value.trim(),
      target_role: searchEl().value.trim(),
    };
  }

  function showError(msg) {
    output.hidden = false;
    outputTitle.textContent = "Something went wrong";
    modeBadge.textContent = "";
    adviceEl.textContent = "";
    jobList.innerHTML = `<div class="error">${escapeHtml(msg)}</div>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderJobs(jobs) {
    if (!jobs || !jobs.length) {
      jobList.innerHTML = "";
      return;
    }
    jobList.innerHTML = jobs.slice(0, 12).map((job) => `
      <article class="job">
        <a class="job-title" href="${escapeHtml(job.url)}" target="_blank" rel="noopener">${escapeHtml(job.title)}</a>
        <div class="job-meta">${escapeHtml(job.company)} · ${escapeHtml(job.category || "Remote")} · ${escapeHtml(job.location || "")}</div>
        <div class="job-actions">
          <button type="button" class="btn ghost cover-btn"
            data-id="${job.id}"
            data-title="${escapeHtml(job.title)}"
            data-company="${escapeHtml(job.company)}"
            data-description="${escapeHtml(job.description || "")}">
            Cover letter
          </button>
        </div>
      </article>
    `).join("");

    jobList.querySelectorAll(".cover-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const body = {
          profile: profileEl().value.trim(),
          job_id: Number(btn.dataset.id),
          job_title: btn.dataset.title,
          company: btn.dataset.company,
          description: btn.dataset.description,
          search: searchEl().value.trim(),
          category: categoryEl().value.trim(),
        };
        if (body.profile.length < 20) {
          showError("Add a longer profile before generating a cover letter.");
          return;
        }
        btn.disabled = true;
        btn.textContent = "Writing…";
        try {
          const res = await fetch("/api/cover-letter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Cover letter failed");
          output.hidden = false;
          outputTitle.textContent = `Cover letter · ${btn.dataset.title}`;
          modeBadge.textContent = data.model_id || "Affine-S6";
          adviceEl.textContent = data.letter;
          window.scrollTo({ top: output.offsetTop - 80, behavior: "smooth" });
        } catch (err) {
          showError(err.message || String(err));
        } finally {
          btn.disabled = false;
          btn.textContent = "Cover letter";
        }
      });
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = payload();
    if (body.profile.length < 20) {
      showError("Please paste a bit more profile text (20+ characters).");
      return;
    }
    matchBtn.disabled = true;
    matchBtn.textContent = "Matching…";
    try {
      const res = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Match failed");
      output.hidden = false;
      outputTitle.textContent = "Match results";
      modeBadge.textContent = data.mode === "affine-s6" ? "Affine-S6" : "Heuristic fallback";
      adviceEl.textContent = data.advice || "";
      renderJobs(data.jobs || []);
      window.scrollTo({ top: output.offsetTop - 80, behavior: "smooth" });
    } catch (err) {
      showError(err.message || String(err));
    } finally {
      matchBtn.disabled = false;
      matchBtn.textContent = "Match with Affine-S6";
    }
  });

  tipsBtn.addEventListener("click", async () => {
    const body = payload();
    if (body.profile.length < 20) {
      showError("Please paste a bit more profile text (20+ characters).");
      return;
    }
    tipsBtn.disabled = true;
    tipsBtn.textContent = "Reviewing…";
    try {
      const res = await fetch("/api/resume-tips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Resume tips failed");
      output.hidden = false;
      outputTitle.textContent = "Resume tips";
      modeBadge.textContent = data.model_id || "Affine-S6";
      adviceEl.textContent = data.tips;
      jobList.innerHTML = "";
      window.scrollTo({ top: output.offsetTop - 80, behavior: "smooth" });
    } catch (err) {
      showError(err.message || String(err));
    } finally {
      tipsBtn.disabled = false;
      tipsBtn.textContent = "Resume tips";
    }
  });
})();
