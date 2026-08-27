import logging
import datetime
from services.pdf_generator import html_to_pdf

logger = logging.getLogger(__name__)

def generate_roadmap_pdf_bytes(roadmap_data, candidate_profile=None):
    """
    Generates a high-quality multi-page A4 PDF from structured career roadmap data.
    Uses CareerPilot brand palette (#524646, #A8A492, #FCF2E5, #EC5B38).
    """
    if not isinstance(roadmap_data, dict):
        roadmap_data = {}

    career_goal = roadmap_data.get("career_goal") or {}
    company = career_goal.get("company") or "Target Tech Company"
    role = career_goal.get("role") or "Target Role"
    readiness = roadmap_data.get("current_readiness") or {}
    score = readiness.get("score", roadmap_data.get("readiness_score", 65))
    summary = readiness.get("summary") or roadmap_data.get("current_profile_summary") or "Personalized career roadmap tailored to your target position."
    duration = roadmap_data.get("roadmap_duration") or roadmap_data.get("estimated_timeline") or "8–12 weeks"
    today_str = datetime.date.today().strftime("%B %d, %Y")

    phases = roadmap_data.get("phases") or roadmap_data.get("roadmap") or []
    projects = roadmap_data.get("recommended_projects") or []
    
    # Collect all unique certifications across phases
    all_certs = []
    seen_certs = set()
    for ph in phases:
        for c in ph.get("certifications", []):
            c_name = c.get("name") if isinstance(c, dict) else str(c)
            if c_name and c_name not in seen_certs:
                seen_certs.add(c_name)
                all_certs.append(c if isinstance(c, dict) else {"name": c_name, "provider": company, "priority": "High", "reason": "Relevant credential", "url": ""})

    # Collect all languages, technologies, tools, core subjects across phases
    all_langs = set()
    all_techs = set()
    all_tools = set()
    all_subjects = set()
    for ph in phases:
        for l in ph.get("languages", []): all_langs.add(l)
        for t in ph.get("technologies", []): all_techs.add(t)
        for tl in ph.get("tools", []): all_tools.add(tl)
        for s in ph.get("core_subjects", []): all_subjects.add(s)

    # Skill Gaps HTML Table
    skill_gaps = roadmap_data.get("skill_gaps") or []
    skill_gaps_html = ""
    if skill_gaps:
        gaps_rows = ""
        for g in skill_gaps:
            g_name = g.get("skill", "Skill")
            g_imp = g.get("importance", "High")
            g_reason = g.get("reason", "")
            g_curr = g.get("current_level", "Beginner")
            g_targ = g.get("target_level", "Job Ready")
            badge_cls = "badge-high" if g_imp.lower() == "high" else ("badge-med" if g_imp.lower() == "medium" else "badge-low")
            gaps_rows += f"""
            <tr>
                <td width="20%"><strong>{g_name}</strong></td>
                <td width="15%"><span class="badge {badge_cls}">{g_imp.upper()}</span></td>
                <td width="35%">{g_reason}</td>
                <td width="15%">{g_curr}</td>
                <td width="15%"><strong>{g_targ}</strong></td>
            </tr>
            """
        skill_gaps_html = f"""
        <div class="section-heading">Priority Skill Gaps & Focus Areas</div>
        <table class="checklist-table" style="font-size: 8pt; margin-bottom: 12px;">
            <tr style="background-color: #FCF2E5; font-weight: bold;">
                <td>Skill</td>
                <td>Importance</td>
                <td>Why Needed</td>
                <td>Current</td>
                <td>Target</td>
            </tr>
            {gaps_rows}
        </table>
        """

    # Competencies Overview Table
    comp_table_html = f"""
    <div class="section-heading">Key Competencies & Target Architecture</div>
    <table width="100%" style="font-size: 8.5pt; margin-bottom: 10px;">
        <tr>
            <td width="50%" valign="top">
                <strong>Programming Languages:</strong><br>
                {', '.join(all_langs) if all_langs else 'N/A'}
            </td>
            <td width="50%" valign="top">
                <strong>Technologies & Frameworks:</strong><br>
                {', '.join(all_techs) if all_techs else 'N/A'}
            </td>
        </tr>
        <tr>
            <td width="50%" valign="top" style="padding-top: 6px;">
                <strong>Developer Tools:</strong><br>
                {', '.join(all_tools) if all_tools else 'N/A'}
            </td>
            <td width="50%" valign="top" style="padding-top: 6px;">
                <strong>Core Academic Subjects:</strong><br>
                {', '.join(all_subjects) if all_subjects else 'N/A'}
            </td>
        </tr>
    </table>
    """

    # Construct Phases HTML
    phases_html = ""
    for idx, ph in enumerate(phases):
        p_num = ph.get("phase_number") or (idx + 1)
        p_title = ph.get("title") or f"Phase {p_num}"
        p_dur = ph.get("duration") or "2 weeks"
        p_obj = ph.get("objective") or ""
        p_milestone = ph.get("milestone") or ""
        
        # Skills list in phase
        skills_html = ""
        for sk in ph.get("skills", []):
            sk_name = sk.get("name") if isinstance(sk, dict) else str(sk)
            sk_priority = sk.get("priority", "High") if isinstance(sk, dict) else "High"
            sk_reason = sk.get("reason", "") if isinstance(sk, dict) else ""
            sk_learn = sk.get("what_to_learn", "") if isinstance(sk, dict) else ""
            
            p_badge_class = "badge-high" if sk_priority.lower() == "high" else ("badge-med" if sk_priority.lower() == "medium" else "badge-low")
            skills_html += f"""
            <div class="skill-item">
                <span class="skill-name"><strong>{sk_name}</strong></span>
                <span class="badge {p_badge_class}">{sk_priority.upper()} PRIORITY</span>
                {f'<div class="skill-sub"><em>Why:</em> {sk_reason}</div>' if sk_reason else ''}
                {f'<div class="skill-sub"><em>What to learn:</em> {sk_learn}</div>' if sk_learn else ''}
            </div>
            """

        phases_html += f"""
        <div class="phase-card">
            <div class="phase-header">
                <table width="100%">
                    <tr>
                        <td class="phase-title">PHASE {p_num}: {p_title}</td>
                        <td class="phase-duration" align="right">{p_dur}</td>
                    </tr>
                </table>
            </div>
            <div class="phase-body">
                {f'<p class="phase-obj"><strong>Objective:</strong> {p_obj}</p>' if p_obj else ''}
                {f'<div class="skills-block">{skills_html}</div>' if skills_html else ''}
                {f'<div class="milestone-box"><strong>Phase Milestone:</strong> {p_milestone}</div>' if p_milestone else ''}
            </div>
        </div>
        """

    # Certifications HTML
    certs_html = ""
    if all_certs:
        for c in all_certs:
            c_name = c.get("name", "Certification")
            c_prov = c.get("provider", company)
            c_prio = c.get("priority", "High")
            c_reason = c.get("reason", "")
            c_url = c.get("url", "")
            
            certs_html += f"""
            <div class="cert-card">
                <table width="100%">
                    <tr>
                        <td><strong>{c_name}</strong> <span class="text-muted">({c_prov})</span></td>
                        <td align="right"><span class="badge badge-high">{c_prio.upper()}</span></td>
                    </tr>
                </table>
                {f'<p class="cert-reason">{c_reason}</p>' if c_reason else ''}
                {f'<p class="cert-url">Official: <a href="{c_url}">{c_url}</a></p>' if c_url else ''}
            </div>
            """
    else:
        certs_html = "<p class='text-muted'>Focus directly on hands-on practical project portfolio demonstration.</p>"

    # Projects HTML
    projects_html = ""
    if projects:
        for idx, pr in enumerate(projects):
            p_title = pr.get("title") if isinstance(pr, dict) else str(pr)
            p_diff = pr.get("difficulty", "Intermediate") if isinstance(pr, dict) else "Intermediate"
            p_skills = ", ".join(pr.get("skills", [])) if isinstance(pr, dict) else ""
            p_build = pr.get("what_to_build", "") if isinstance(pr, dict) else ""
            p_out = pr.get("expected_outcome", "") if isinstance(pr, dict) else ""
            
            projects_html += f"""
            <div class="project-card">
                <table width="100%">
                    <tr>
                        <td class="project-title">Project {idx+1}: {p_title}</td>
                        <td align="right"><span class="badge badge-med">{p_diff.upper()}</span></td>
                    </tr>
                </table>
                {f'<p class="project-meta"><strong>Skills Applied:</strong> {p_skills}</p>' if p_skills else ''}
                {f'<p class="project-desc"><strong>What to build:</strong> {p_build}</p>' if p_build else ''}
                {f'<p class="project-outcome"><strong>Outcome:</strong> {p_out}</p>' if p_out else ''}
            </div>
            """
    else:
        projects_html = "<p class='text-muted'>Build production-ready GitHub repositories demonstrating role skills.</p>"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{
            size: a4 portrait;
            margin: 0.4in;
        }}
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 9.5pt;
            line-height: 1.4;
            color: #524646;
            background-color: #FFFFFF;
        }}
        .header-table {{
            width: 100%;
            border-bottom: 2px solid #EC5B38;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }}
        .brand-title {{
            font-size: 16pt;
            font-weight: bold;
            color: #EC5B38;
        }}
        .brand-sub {{
            font-size: 8.5pt;
            color: #A8A492;
        }}
        .doc-title {{
            font-size: 13pt;
            font-weight: bold;
            color: #524646;
            text-align: right;
        }}
        .doc-date {{
            font-size: 8pt;
            color: #A8A492;
            text-align: right;
        }}
        .hero-card {{
            background-color: #FCF2E5;
            border: 1px solid #A8A492;
            padding: 10px 14px;
            margin-bottom: 14px;
        }}
        .goal-title {{
            font-size: 13pt;
            font-weight: bold;
            color: #524646;
        }}
        .goal-company {{
            font-size: 10.5pt;
            color: #EC5B38;
            font-weight: bold;
        }}
        .score-val {{
            font-size: 18pt;
            font-weight: bold;
            color: #EC5B38;
            text-align: right;
        }}
        .section-heading {{
            font-size: 11pt;
            font-weight: bold;
            color: #524646;
            border-bottom: 1px solid #A8A492;
            padding-bottom: 3px;
            margin-top: 14px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }}
        .phase-card {{
            border: 1px solid #A8A492;
            margin-bottom: 10px;
        }}
        .phase-header {{
            background-color: #524646;
            color: #FCF2E5;
            padding: 5px 10px;
            font-weight: bold;
        }}
        .phase-title {{
            color: #FCF2E5;
            font-size: 10pt;
        }}
        .phase-duration {{
            color: #FCF2E5;
            font-size: 8.5pt;
        }}
        .phase-body {{
            padding: 8px 10px;
            background-color: #FFFFFF;
        }}
        .phase-obj {{
            font-size: 9pt;
            color: #524646;
            margin-bottom: 6px;
        }}
        .skill-item {{
            margin-bottom: 4px;
            padding-left: 8px;
            border-left: 2px solid #EC5B38;
        }}
        .skill-name {{
            font-size: 9pt;
            color: #524646;
        }}
        .skill-sub {{
            font-size: 8pt;
            color: #524646;
            margin-left: 4px;
        }}
        .milestone-box {{
            background-color: #FCF2E5;
            padding: 5px 8px;
            font-size: 8.5pt;
            margin-top: 6px;
            border: 1px dashed #A8A492;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            font-size: 7pt;
            font-weight: bold;
            border-radius: 3px;
        }}
        .badge-high {{
            background-color: #ffebee;
            color: #c62828;
        }}
        .badge-med {{
            background-color: #fff3e0;
            color: #e65100;
        }}
        .badge-low {{
            background-color: #e8f5e9;
            color: #2e7d32;
        }}
        .project-card, .cert-card {{
            border: 1px solid #A8A492;
            background-color: #FFFFFF;
            padding: 7px 10px;
            margin-bottom: 8px;
        }}
        .project-title {{
            font-size: 9.5pt;
            font-weight: bold;
            color: #524646;
        }}
        .project-meta, .project-desc, .project-outcome, .cert-reason, .cert-url {{
            font-size: 8.5pt;
            margin-top: 3px;
            color: #524646;
        }}
        .checklist-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 6px;
        }}
        .checklist-table td {{
            padding: 4px 6px;
            font-size: 8.5pt;
            border-bottom: 1px solid #FCF2E5;
        }}
        .page-break {{
            page-break-before: always;
        }}
        .text-muted {{
            color: #A8A492;
        }}
        .footer-banner {{
            margin-top: 14px;
            padding: 8px;
            background-color: #524646;
            color: #FCF2E5;
            text-align: center;
            font-size: 8pt;
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <table class="header-table">
        <tr>
            <td width="55%">
                <div class="brand-title">CareerPilot AI</div>
                <div class="brand-sub">Personalized Career Strategy & Learning Plan</div>
            </td>
            <td width="45%">
                <div class="doc-title">PERSONALIZED ROADMAP</div>
                <div class="doc-date">Generated: {today_str}</div>
            </td>
        </tr>
    </table>

    <!-- Hero Card -->
    <div class="hero-card">
        <table width="100%">
            <tr>
                <td width="70%">
                    <div class="goal-company">{company}</div>
                    <div class="goal-title">{role}</div>
                    <div style="font-size: 8.5pt; color: #524646; margin-top: 4px;"><strong>Estimated Timeline:</strong> {duration}</div>
                </td>
                <td width="30%" align="right">
                    <div style="font-size: 8pt; color: #A8A492; text-transform: uppercase;">Readiness Score</div>
                    <div class="score-val">{score}/100</div>
                </td>
            </tr>
        </table>
    </div>

    <!-- Career Objective / Overview -->
    <div class="section-heading">Career Strategy & Objective</div>
    <p style="font-size: 9pt; margin-bottom: 10px;">{summary}</p>

    <!-- Priority Skill Gaps Table -->
    {skill_gaps_html}

    <!-- Competencies Overview Table -->
    {comp_table_html}

    <!-- Sequential Roadmap Phases -->
    <div class="section-heading">Sequential Milestone Roadmap</div>
    {phases_html}

    <!-- Page Break for Projects & Certifications -->
    <div class="page-break"></div>

    <!-- Header Page 2 -->
    <table class="header-table">
        <tr>
            <td width="55%">
                <div class="brand-title">CareerPilot AI</div>
                <div class="brand-sub">{company} — {role}</div>
            </td>
            <td width="45%" align="right">
                <div class="doc-title">PORTFOLIO & CERTIFICATIONS</div>
            </td>
        </tr>
    </table>

    <!-- Recommended Certifications -->
    <div class="section-heading">Relevant Industry Certifications</div>
    {certs_html}

    <!-- Portfolio Projects -->
    <div class="section-heading">Portfolio Project Roadmap</div>
    {projects_html}

    <!-- Final Job-Ready Checklist -->
    <div class="section-heading">Final Job-Ready Checklist</div>
    <table class="checklist-table">
        <tr>
            <td width="5%">[ ✓ ]</td>
            <td width="95%"><strong>Required Programming Languages & Core Topics Mastered</strong></td>
        </tr>
        <tr>
            <td>[ ✓ ]</td>
            <td><strong>Essential Developer Tools & Container Technologies Verified</strong></td>
        </tr>
        <tr>
            <td>[ ✓ ]</td>
            <td><strong>2+ Portfolio Projects Deployed to Public GitHub & Documented</strong></td>
        </tr>
        <tr>
            <td>[ ✓ ]</td>
            <td><strong>Industry Certification Syllabus or Credential Completed</strong></td>
        </tr>
        <tr>
            <td>[ ✓ ]</td>
            <td><strong>Resume Tailored & ATS-Optimized for {company}</strong></td>
        </tr>
        <tr>
            <td>[ ✓ ]</td>
            <td><strong>Technical & Behavioral Interview Prep Sessions Completed</strong></td>
        </tr>
    </table>

    <div class="footer-banner">
        CareerPilot AI — Your personalized path from current skills to career readiness.
    </div>
</body>
</html>
"""

    return html_to_pdf(html_content)
