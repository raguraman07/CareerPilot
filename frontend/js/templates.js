// 10 Resume Templates Definitions & Compiler Engine

const RESUME_TEMPLATES = {
    // 1. Modern Professional
    modern_professional: function(data, style) {
        const primary = style.primaryColor || '#6366f1';
        const font = style.fontFamily || 'Inter';
        const spacing = getSpacingSize(style.spacing);
        const colLayout = style.layout || 'two';

        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.4; color: #2d3748; padding: 10px;">
                <!-- Header -->
                <div style="border-bottom: 3px solid ${primary}; padding-bottom: 12px; margin-bottom: 20px;">
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                        <tr>
                            ${data.personalInfo.photo ? `
                            <td style="width: 75px; padding-right: 15px; vertical-align: middle;">
                                <img src="${data.personalInfo.photo}" style="width: 65px; height: 65px; border-radius: 50%; object-fit: cover; border: 2px solid ${primary};">
                            </td>
                            ` : ''}
                            <td style="vertical-align: middle;">
                                <h1 style="font-family: 'Poppins', sans-serif; font-size: 26pt; margin: 0 0 4px 0; color: #1a202c; font-weight: 800;">${data.personalInfo.fullName || 'John Doe'}</h1>
                                <h2 style="font-size: 13pt; font-weight: 600; margin: 0; color: ${primary}; text-transform: uppercase; letter-spacing: 0.05em;">${data.personalInfo.jobTitle || 'Professional Role'}</h2>
                            </td>
                        </tr>
                    </table>
                    
                    <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt; color: #4a5568;">
                        <tr>
                            <td style="padding: 2px 0; vertical-align: top;">
                                ${data.personalInfo.email ? `Email: ${data.personalInfo.email} ` : ''}
                                ${data.personalInfo.phone ? ` &bull; Phone: ${data.personalInfo.phone} ` : ''}
                                ${data.personalInfo.address ? ` &bull; Loc: ${data.personalInfo.address}` : ''}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 2px 0; vertical-align: top;">
                                ${data.personalInfo.linkedIn ? `LinkedIn: ${data.personalInfo.linkedIn} ` : ''}
                                ${data.personalInfo.github ? ` &bull; GitHub: ${data.personalInfo.github} ` : ''}
                                ${data.personalInfo.portfolio ? ` &bull; Web: ${data.personalInfo.portfolio}` : ''}
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- Summary -->
                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing};">
                        <p style="font-size: 10pt; font-style: italic; color: #4a5568; margin: 0; line-height: 1.5;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Body Columns -->
                ${colLayout === 'two' ? `
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <!-- Left Main Column -->
                            <td style="width: 63%; vertical-align: top; padding-right: 20px;">
                                ${renderWorkExperience(data.experience, spacing, primary)}
                                ${renderProjects(data.projects, spacing, primary)}
                            </td>
                            <!-- Right Sidebar -->
                            <td style="width: 37%; vertical-align: top; border-left: 1px solid #e2e8f0; padding-left: 20px;">
                                ${renderEducation(data.education, spacing, primary)}
                                ${renderSkills(data.skills, spacing, primary)}
                                ${renderCertifications(data.certifications, spacing, primary)}
                                ${renderCustomSections(data.customSections, spacing, primary)}
                            </td>
                        </tr>
                    </table>
                ` : `
                    <div>
                        ${renderWorkExperience(data.experience, spacing, primary)}
                        ${renderProjects(data.projects, spacing, primary)}
                        ${renderEducation(data.education, spacing, primary)}
                        ${renderSkills(data.skills, spacing, primary)}
                        ${renderCertifications(data.certifications, spacing, primary)}
                        ${renderCustomSections(data.customSections, spacing, primary)}
                    </div>
                `}
            </div>
        `;
    },

    // 2. Minimal ATS
    minimal_ats: function(data, style) {
        const font = style.fontFamily || 'Inter';
        const spacing = getSpacingSize(style.spacing);

        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.3; color: #000000; padding: 5px;">
                <div style="margin-bottom: 15px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="vertical-align: middle; text-align: ${data.personalInfo.photo ? 'left' : 'center'};">
                                <h1 style="font-size: 20pt; font-weight: bold; margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.05em; color: #000000;">${data.personalInfo.fullName || 'John Doe'}</h1>
                                <div style="font-size: 9.5pt;">
                                    ${data.personalInfo.address ? `${data.personalInfo.address} &bull; ` : ''} 
                                    ${data.personalInfo.phone ? `${data.personalInfo.phone} &bull; ` : ''} 
                                    ${data.personalInfo.email ? `${data.personalInfo.email}` : ''}
                                </div>
                                <div style="font-size: 9.5pt; margin-top: 2px;">
                                    ${data.personalInfo.linkedIn ? `LinkedIn: ${data.personalInfo.linkedIn} &bull; ` : ''}
                                    ${data.personalInfo.github ? `GitHub: ${data.personalInfo.github} &bull; ` : ''}
                                    ${data.personalInfo.portfolio ? `Portfolio: ${data.personalInfo.portfolio}` : ''}
                                </div>
                            </td>
                            ${data.personalInfo.photo ? `
                            <td style="width: 70px; text-align: right; vertical-align: middle; padding-left: 15px;">
                                <img src="${data.personalInfo.photo}" style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover;">
                            </td>
                            ` : ''}
                        </tr>
                    </table>
                </div>

                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 6px; letter-spacing: 0.05em;">Professional Summary</div>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.4;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Experience -->
                ${data.experience && data.experience.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">Experience</div>
                        ${data.experience.map(exp => `
                            <div style="margin-bottom: 10px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                                    <tr>
                                        <td style="font-weight: bold; width: 70%; vertical-align: top;">${exp.role} - ${exp.company}</td>
                                        <td style="text-align: right; font-style: italic; width: 30%; vertical-align: top;">${exp.startDate} – ${exp.endDate || 'Present'}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 4px 0 0 0; white-space: pre-line; line-height: 1.4; color: #111827;">${exp.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Projects -->
                ${data.projects && data.projects.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">Projects</div>
                        ${data.projects.map(proj => `
                            <div style="margin-bottom: 8px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                                    <tr>
                                        <td style="font-weight: bold; width: 70%; vertical-align: top;">
                                            ${proj.name} ${proj.liveUrl ? `(${proj.liveUrl})` : ''}
                                        </td>
                                        <td style="text-align: right; font-style: italic; width: 30%; vertical-align: top;">${proj.technologiesUsed || ''}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 2px 0 0 0; line-height: 1.4; color: #111827;">${proj.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Education -->
                ${data.education && data.education.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">Education</div>
                        ${data.education.map(edu => `
                            <div style="margin-bottom: 8px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                                    <tr>
                                        <td style="font-weight: bold; width: 75%; vertical-align: top;">${edu.degree}</td>
                                        <td style="text-align: right; font-style: italic; width: 25%; vertical-align: top;">${edu.startDate} – ${edu.endDate || 'Present'}</td>
                                    </tr>
                                    <tr>
                                        <td colspan="2" style="font-style: italic;">${edu.institution} ${edu.grade ? `(Grade: ${edu.grade})` : ''}</td>
                                    </tr>
                                </table>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Skills -->
                ${data.skills && data.skills.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">Skills</div>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.4;">
                            ${data.skills.map(s => {
                                const cat = s.name;
                                const tags = s.tags && s.tags.length > 0 ? `: ${s.tags.join(', ')}` : '';
                                return `<strong>${cat}</strong>${tags}`;
                            }).join(' &nbsp;|&nbsp; ')}
                        </p>
                    </div>
                ` : ''}
                
                <!-- Certifications -->
                ${data.certifications && data.certifications.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">Certifications</div>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.4;">${data.certifications.join(', ')}</p>
                    </div>
                ` : ''}

                <!-- Custom Sections -->
                ${data.customSections && data.customSections.length > 0 ? `
                    ${data.customSections.map(sect => `
                        <div style="margin-bottom: ${spacing};">
                            <div style="font-weight: bold; text-transform: uppercase; font-size: 10pt; border-bottom: 1px solid #000000; margin-bottom: 8px; letter-spacing: 0.05em;">${sect.sectionTitle || 'Custom Section'}</div>
                            <p style="font-size: 9.5pt; margin: 0; white-space: pre-line; line-height: 1.4;">${sect.sectionContent || ''}</p>
                        </div>
                    `).join('')}
                ` : ''}
            </div>
        `;
    },

    // 3. Executive Style
    executive: function(data, style) {
        const primary = style.primaryColor || '#1e3a8a';
        const font = style.fontFamily || 'Montserrat';
        const spacing = getSpacingSize(style.spacing);
        
        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.4; color: #1f2937; padding: 15px;">
                <!-- Header -->
                <div style="text-align: center; border-bottom: 2px double ${primary}; padding-bottom: 14px; margin-bottom: 24px;">
                    ${data.personalInfo.photo ? `
                    <div style="text-align: center; margin-bottom: 12px;">
                        <img src="${data.personalInfo.photo}" style="width: 75px; height: 75px; border-radius: 50%; border: 2px solid ${primary}; object-fit: cover;">
                    </div>
                    ` : ''}
                    <h1 style="font-size: 26pt; font-weight: 700; color: ${primary}; letter-spacing: 0.05em; margin: 0 0 6px 0;">${data.personalInfo.fullName || 'John Doe'}</h1>
                    <h2 style="font-size: 12pt; letter-spacing: 0.1em; color: #6b7280; font-weight: 500; text-transform: uppercase; margin: 0 0 12px 0;">${data.personalInfo.jobTitle || 'Executive Professional'}</h2>
                    <div style="font-size: 9.5pt; color: #4b5563;">
                        ${data.personalInfo.address ? `${data.personalInfo.address} &bull; ` : ''} 
                        ${data.personalInfo.phone ? `${data.personalInfo.phone} &bull; ` : ''} 
                        ${data.personalInfo.email ? `${data.personalInfo.email}` : ''}
                    </div>
                    <div style="font-size: 9.5pt; color: #4b5563; margin-top: 4px;">
                        ${data.personalInfo.linkedIn ? `LinkedIn: ${data.personalInfo.linkedIn}` : ''}
                        ${data.personalInfo.github ? ` &bull; GitHub: ${data.personalInfo.github}` : ''}
                        ${data.personalInfo.portfolio ? ` &bull; Portfolio: ${data.personalInfo.portfolio}` : ''}
                    </div>
                </div>

                <!-- Summary -->
                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing}; text-align: justify;">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 10px 0; letter-spacing: 0.05em;">Executive Profile</h3>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.5;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Experience -->
                ${data.experience && data.experience.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">Professional Background</h3>
                        ${data.experience.map(exp => `
                            <div style="margin-bottom: 14px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt; margin-bottom: 4px;">
                                    <tr>
                                        <td style="font-weight: bold; color: #111827; width: 70%; vertical-align: top;">${exp.role} @ ${exp.company}</td>
                                        <td style="text-align: right; font-weight: bold; color: ${primary}; width: 30%; vertical-align: top;">${exp.startDate} – ${exp.endDate || 'Present'}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 0; white-space: pre-line; text-align: justify; line-height: 1.5; color: #374151;">${exp.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Projects -->
                ${data.projects && data.projects.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">Key Initiatives & Projects</h3>
                        ${data.projects.map(proj => `
                            <div style="margin-bottom: 12px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt; margin-bottom: 4px;">
                                    <tr>
                                        <td style="font-weight: bold; color: #111827; width: 65%; vertical-align: top;">
                                            ${proj.name} ${proj.liveUrl ? ` <span style="font-weight: normal; font-size: 8.5pt;"><a href="${proj.liveUrl}" target="_blank" style="color: ${primary};">[Link]</a></span>` : ''}
                                        </td>
                                        <td style="text-align: right; font-style: italic; color: #4b5563; width: 35%; vertical-align: top;">${proj.technologiesUsed || ''}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 0; line-height: 1.5; color: #374151;">${proj.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Education -->
                ${data.education && data.education.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">Education & Credentials</h3>
                        ${data.education.map(edu => `
                            <div style="margin-bottom: 8px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                                    <tr>
                                        <td style="font-weight: bold; width: 75%; vertical-align: top;">${edu.degree}</td>
                                        <td style="text-align: right; font-style: italic; width: 25%; vertical-align: top;">${edu.startDate} – ${edu.endDate || 'Present'}</td>
                                    </tr>
                                    <tr>
                                        <td colspan="2" style="color: #4b5563;">${edu.institution} ${edu.grade ? `| Grade: ${edu.grade}` : ''}</td>
                                    </tr>
                                </table>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Skills -->
                ${data.skills && data.skills.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">Core Expertise</h3>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.5;">
                            ${data.skills.map(s => {
                                const cat = s.name;
                                const tags = s.tags && s.tags.length > 0 ? `: ${s.tags.join(', ')}` : '';
                                return `<strong>${cat}</strong>${tags}`;
                            }).join(' &bull; ')}
                        </p>
                    </div>
                ` : ''}

                <!-- Certifications -->
                ${data.certifications && data.certifications.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">Professional Certifications</h3>
                        <ul style="margin: 0; padding-left: 20px; font-size: 9.5pt; color: #374151; line-height: 1.5;">
                            ${data.certifications.map(cert => `<li style="margin-bottom: 4px;">${cert}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                <!-- Custom Sections -->
                ${data.customSections && data.customSections.length > 0 ? `
                    ${data.customSections.map(sect => `
                        <div style="margin-bottom: ${spacing};">
                            <h3 style="font-size: 11pt; color: ${primary}; text-transform: uppercase; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin: 0 0 12px 0; letter-spacing: 0.05em;">${sect.sectionTitle || 'Custom Section'}</h3>
                            <p style="font-size: 9.5pt; margin: 0; white-space: pre-line; line-height: 1.5; color: #374151;">${sect.sectionContent || ''}</p>
                        </div>
                    `).join('')}
                ` : ''}
            </div>
        `;
    },

    // 4. Creative Designer
    creative_designer: function(data, style) {
        const primary = style.primaryColor || '#8b5cf6';
        const secondary = style.secondaryColor || '#ec4899';
        const font = style.fontFamily || 'Poppins';
        const spacing = getSpacingSize(style.spacing);

        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.4; color: #374151; padding: 0;">
                <!-- Gradient Header with Table Contact block -->
                <div style="background: linear-gradient(135deg, ${primary} 0%, ${secondary} 100%); padding: 25px; border-radius: 8px 8px 0 0; color: #ffffff; margin-bottom: 20px;">
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
                        <tr>
                            <td style="vertical-align: middle;">
                                <h1 style="font-size: 28pt; font-weight: 800; margin: 0 0 4px 0; color: #ffffff;">${data.personalInfo.fullName || 'John Doe'}</h1>
                                <h2 style="font-size: 13pt; font-weight: 500; margin: 0; color: rgba(255,255,255,0.9); text-transform: uppercase; letter-spacing: 0.05em;">${data.personalInfo.jobTitle || 'UI/UX Designer'}</h2>
                            </td>
                            ${data.personalInfo.photo ? `
                            <td style="width: 75px; text-align: right; vertical-align: middle; padding-left: 15px;">
                                <img src="${data.personalInfo.photo}" style="width: 65px; height: 65px; border-radius: 8px; border: 2.5px solid rgba(255,255,255,0.3); object-fit: cover;">
                            </td>
                            ` : ''}
                        </tr>
                    </table>
                    
                    <table style="width: 100%; border-collapse: collapse; font-size: 9pt; color: #ffffff;">
                        <tr>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0;">
                                ${data.personalInfo.email ? `Email: ${data.personalInfo.email}` : ''}
                            </td>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0; text-align: right;">
                                ${data.personalInfo.phone ? `Phone: ${data.personalInfo.phone}` : ''}
                            </td>
                        </tr>
                        <tr>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0;">
                                ${data.personalInfo.address ? `Loc: ${data.personalInfo.address}` : ''}
                            </td>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0; text-align: right;">
                                ${data.personalInfo.portfolio ? `Web: ${data.personalInfo.portfolio}` : ''}
                            </td>
                        </tr>
                        <tr>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0;">
                                ${data.personalInfo.linkedIn ? `LinkedIn: ${data.personalInfo.linkedIn}` : ''}
                            </td>
                            <td style="width: 50%; vertical-align: top; padding: 2px 0; text-align: right;">
                                ${data.personalInfo.github ? `GitHub: ${data.personalInfo.github}` : ''}
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="padding: 10px 20px;">
                    <!-- Summary -->
                    ${data.personalInfo.summary ? `
                        <div style="margin-bottom: ${spacing}; background: #f3e8ff; border-left: 4px solid ${primary}; padding: 12px 16px; border-radius: 0 8px 8px 0;">
                            <p style="font-size: 9.5pt; color: #5b21b6; margin: 0; line-height: 1.5;">${data.personalInfo.summary}</p>
                        </div>
                    ` : ''}

                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <!-- Left Column: Work & Projects -->
                            <td style="width: 60%; vertical-align: top; padding-right: 20px;">
                                ${renderWorkExperience(data.experience, spacing, primary)}
                                ${renderProjects(data.projects, spacing, primary)}
                            </td>
                            <!-- Right Column: Education & Skills -->
                            <td style="width: 40%; vertical-align: top; padding-left: 20px; border-left: 1px solid #f3f4f6;">
                                ${renderSkills(data.skills, spacing, primary)}
                                ${renderEducation(data.education, spacing, primary)}
                                ${renderCertifications(data.certifications, spacing, primary)}
                                ${renderCustomSections(data.customSections, spacing, primary)}
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
        `;
    },

    // 5. Developer Portfolio
    developer_portfolio: function(data, style) {
        const primary = style.primaryColor || '#10b981';
        const font = style.fontFamily || 'Fira Code';
        const spacing = getSpacingSize(style.spacing);

        return `
            <div style="font-family: '${font}', monospace; line-height: 1.4; color: #111827; padding: 10px;">
                <!-- Terminal Header style -->
                <div style="background: #1f2937; color: #34d399; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
                    <div style="color: #ef4444; font-size: 18px; margin-bottom: 8px;">&bull;&bull;&bull; <span style="color: #9ca3af; font-size: 10pt; margin-left: 8px;">terminal - resume</span></div>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="vertical-align: top;">
                                <div style="font-size: 16pt; font-weight: bold; color: #10b981;">$ cat dev_details.json</div>
                                <div style="margin-top: 10px; font-size: 9.5pt; color: #e5e7eb; font-family: '${font}', monospace;">
                                    {<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;"name": "${data.personalInfo.fullName || 'John Doe'}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;"title": "${data.personalInfo.jobTitle || 'DevOps / Backend Engineer'}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;"contact": {<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"email": "${data.personalInfo.email || ''}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"phone": "${data.personalInfo.phone || ''}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"address": "${data.personalInfo.address || ''}"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;},<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;"socials": {<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"github": "${data.personalInfo.github || ''}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"linkedin": "${data.personalInfo.linkedIn || ''}",<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"web": "${data.personalInfo.portfolio || ''}"<br>
                                    &nbsp;&nbsp;&nbsp;&nbsp;}<br>
                                    }
                                </div>
                            </td>
                            ${data.personalInfo.photo ? `
                            <td style="width: 75px; text-align: right; vertical-align: top; padding-left: 15px;">
                                <img src="${data.personalInfo.photo}" style="width: 65px; height: 65px; border-radius: 4px; border: 1px solid #10b981; object-fit: cover;">
                            </td>
                            ` : ''}
                        </tr>
                    </table>
                </div>

                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 6px;"># PROFILE_SUMMARY</div>
                        <p style="font-size: 9.5pt; margin: 0; color: #4b5563; line-height: 1.5;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Experience -->
                ${data.experience && data.experience.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 10px;"># EXPERIENCE_HISTORY</div>
                        ${data.experience.map(exp => `
                            <div style="margin-bottom: 14px; border-left: 2px dashed ${primary}; padding-left: 12px; margin-left: 4px;">
                                <div style="font-weight: bold; font-size: 10pt; color: #111827;">${exp.role} @ <span style="color: ${primary};">${exp.company}</span></div>
                                <div style="font-size: 8.5pt; color: #6b7280; margin-bottom: 4px;">[${exp.startDate} - ${exp.endDate || 'Present'}]</div>
                                <p style="font-size: 9.5pt; margin: 0; color: #374151; line-height: 1.4;">${exp.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Tech Stacks Table Grid (No Flexbox) -->
                ${data.skills && data.skills.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 10px;"># TECH_STACKS</div>
                        <table style="width: 100%; border-collapse: collapse;">
                            ${data.skills.map(s => {
                                const skillName = s.name;
                                const tags = s.tags && s.tags.length > 0 ? s.tags.join(', ') : '';
                                return `
                                    <tr style="border-bottom: 1px solid #e5e7eb;">
                                        <td style="width: 30%; font-weight: bold; font-size: 9.5pt; color: #111827; padding: 6px 0; vertical-align: top;">
                                            &gt; ${skillName}
                                        </td>
                                        <td style="width: 70%; font-size: 9.5pt; color: #4b5563; padding: 6px 0; vertical-align: top;">
                                            ${tags}
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </table>
                    </div>
                ` : ''}

                <!-- Projects -->
                ${data.projects && data.projects.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 10px;"># FEATURED_PROJECTS</div>
                        ${data.projects.map(proj => `
                            <div style="margin-bottom: 12px; background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px; border-radius: 6px;">
                                <div style="font-weight: bold; font-size: 9.5pt; color: #111827;">${proj.name}</div>
                                <div style="font-size: 8.5pt; color: ${primary}; margin: 2px 0;">[Stack: ${proj.technologiesUsed || 'n/a'}]</div>
                                ${proj.liveUrl ? `<div style="font-size: 8.5pt; margin: 2px 0;"><a href="${proj.liveUrl}" target="_blank" style="color:#2563eb; text-decoration:none;">URL: ${proj.liveUrl}</a></div>` : ''}
                                <p style="font-size: 9pt; margin: 4px 0 0 0; color: #4b5563; line-height: 1.4;">${proj.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                
                <!-- Education -->
                ${data.education && data.education.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 8px;"># EDUCATION</div>
                        ${data.education.map(edu => `
                            <div style="font-size: 9.5pt; margin-bottom: 6px; color: #374151;">
                                &gt; <strong>${edu.degree}</strong> - ${edu.institution} [${edu.startDate} - ${edu.endDate || 'Present'}] ${edu.grade ? `(GPA: ${edu.grade})` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Certifications -->
                ${data.certifications && data.certifications.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <div style="color: ${primary}; font-weight: bold; margin-bottom: 8px;"># CERTIFICATIONS</div>
                        <ul style="margin: 0; padding-left: 20px; font-size: 9.5pt; color: #4b5563;">
                            ${data.certifications.map(cert => `<li style="margin-bottom: 4px;">${cert}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                <!-- Custom Sections -->
                ${data.customSections && data.customSections.length > 0 ? `
                    ${data.customSections.map(sect => `
                        <div style="margin-bottom: ${spacing};">
                            <div style="color: ${primary}; font-weight: bold; margin-bottom: 8px;"># ${sect.sectionTitle ? sect.sectionTitle.toUpperCase().replace(/\s+/g, '_') : 'CUSTOM_SECTION'}</div>
                            <p style="font-size: 9.5pt; margin: 0; color: #4b5563; white-space: pre-line; line-height: 1.4;">${sect.sectionContent || ''}</p>
                        </div>
                    `).join('')}
                ` : ''}
            </div>
        `;
    },

    // 6. Corporate
    corporate: function(data, style) {
        const primary = style.primaryColor || '#1e293b';
        const font = style.fontFamily || 'Roboto';
        const spacing = getSpacingSize(style.spacing);

        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.4; color: #334155; padding: 10px;">
                <!-- Corporate Elegant Header -->
                <table style="width: 100%; border-collapse: collapse; border-bottom: 2px solid ${primary}; padding-bottom: 16px; margin-bottom: 20px;">
                    <tr>
                        ${data.personalInfo.photo ? `
                        <td style="width: 75px; vertical-align: middle; padding-right: 15px;">
                            <img src="${data.personalInfo.photo}" style="width: 65px; height: 65px; border-radius: 4px; border: 1.5px solid ${primary}; object-fit: cover;">
                        </td>
                        ` : ''}
                        <td style="vertical-align: middle; width: 55%;">
                            <h1 style="font-size: 24pt; font-weight: 700; color: ${primary}; text-transform: uppercase; letter-spacing: -0.01em; margin: 0;">${data.personalInfo.fullName || 'John Doe'}</h1>
                            <h2 style="font-size: 12pt; font-weight: 600; color: #475569; margin: 4px 0 0 0; text-transform: uppercase; letter-spacing: 0.05em;">${data.personalInfo.jobTitle || 'Corporate Professional'}</h2>
                        </td>
                        <td style="text-align: right; vertical-align: middle; font-size: 9pt; color: #475569; width: 40%; line-height: 1.4;">
                            <div>${data.personalInfo.email || ''}</div>
                            <div>${data.personalInfo.phone || ''}</div>
                            <div>${data.personalInfo.address || ''}</div>
                            ${data.personalInfo.linkedIn ? `<div>LinkedIn: ${data.personalInfo.linkedIn}</div>` : ''}
                            ${data.personalInfo.portfolio ? `<div>Web: ${data.personalInfo.portfolio}</div>` : ''}
                        </td>
                    </tr>
                </table>

                <!-- Summary -->
                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing};">
                        <p style="font-size: 9.5pt; margin: 0; text-align: justify; line-height: 1.5; color: #334155;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Experience -->
                ${data.experience && data.experience.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">Work History</h3>
                        ${data.experience.map(exp => `
                            <div style="margin-bottom: 14px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt; font-weight: 600; margin-bottom: 4px;">
                                    <tr>
                                        <td style="color: #0f172a; width: 70%; vertical-align: top;">${exp.role} &mdash; ${exp.company}</td>
                                        <td style="text-align: right; color: #64748b; width: 30%; vertical-align: top;">${exp.startDate} - ${exp.endDate || 'Present'}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 0; text-align: justify; line-height: 1.5; color: #475569;">${exp.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Projects -->
                ${data.projects && data.projects.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">Key Projects</h3>
                        ${data.projects.map(proj => `
                            <div style="margin-bottom: 12px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt; font-weight: 600; margin-bottom: 4px;">
                                    <tr>
                                        <td style="color: #0f172a; width: 65%; vertical-align: top;">${proj.name} ${proj.liveUrl ? ` <span style="font-weight:normal; font-size:8.5pt;"><a href="${proj.liveUrl}" target="_blank" style="color:${primary};">[URL]</a></span>` : ''}</td>
                                        <td style="text-align: right; color: #64748b; width: 35%; vertical-align: top; font-weight: normal; font-style: italic;">${proj.technologiesUsed || ''}</td>
                                    </tr>
                                </table>
                                <p style="font-size: 9.5pt; margin: 0; line-height: 1.5; color: #475569;">${proj.description}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Education -->
                ${data.education && data.education.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">Academic Education</h3>
                        ${data.education.map(edu => `
                            <div style="margin-bottom: 8px;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                                    <tr>
                                        <td style="font-weight: 600; width: 75%; vertical-align: top; color: #0f172a;">${edu.degree}</td>
                                        <td style="text-align: right; font-style: italic; width: 25%; vertical-align: top; color: #64748b;">${edu.startDate} - ${edu.endDate || 'Present'}</td>
                                    </tr>
                                    <tr>
                                        <td colspan="2" style="color: #64748b;">${edu.institution} ${edu.grade ? `| Grade: ${edu.grade}` : ''}</td>
                                    </tr>
                                </table>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <!-- Skills -->
                ${data.skills && data.skills.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">Professional Skills</h3>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.5;">
                            ${data.skills.map(s => {
                                const cat = s.name;
                                const tags = s.tags && s.tags.length > 0 ? `: ${s.tags.join(', ')}` : '';
                                return `<strong>${cat}</strong>${tags}`;
                            }).join(' &bull; ')}
                        </p>
                    </div>
                ` : ''}

                <!-- Certifications -->
                ${data.certifications && data.certifications.length > 0 ? `
                    <div style="margin-bottom: ${spacing};">
                        <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">Certifications</h3>
                        <p style="font-size: 9.5pt; margin: 0; line-height: 1.5; color: #475569;">${data.certifications.join(', ')}</p>
                    </div>
                ` : ''}

                <!-- Custom Sections -->
                ${data.customSections && data.customSections.length > 0 ? `
                    ${data.customSections.map(sect => `
                        <div style="margin-bottom: ${spacing};">
                            <h3 style="font-size: 11pt; color: ${primary}; border-left: 4px solid ${primary}; padding-left: 8px; text-transform: uppercase; font-weight: 700; margin: 0 0 12px 0; letter-spacing: 0.05em;">${sect.sectionTitle || 'Custom Section'}</h3>
                            <p style="font-size: 9.5pt; margin: 0; white-space: pre-line; line-height: 1.5; color: #475569;">${sect.sectionContent || ''}</p>
                        </div>
                    `).join('')}
                ` : ''}
            </div>
        `;
    },

    // 7. Elegant Dark (Premium Dark-mode Theme)
    elegant_dark: function(data, style) {
        const primary = style.primaryColor || '#06b6d4'; // Sky cyan
        const font = style.fontFamily || 'Poppins';
        const spacing = getSpacingSize(style.spacing);

        return `
            <div style="font-family: '${font}', sans-serif; line-height: 1.4; color: #e2e8f0; background-color: #0f172a; margin: -0.5in; padding: 0.5in; min-height: 11in; box-sizing: border-box;">
                <!-- Header -->
                <div style="border-bottom: 2px solid ${primary}; padding-bottom: 20px; margin-bottom: 25px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            ${data.personalInfo.photo ? `
                            <td style="width: 75px; vertical-align: middle; padding-right: 15px;">
                                <img src="${data.personalInfo.photo}" style="width: 65px; height: 65px; border-radius: 50%; border: 2px solid ${primary}; object-fit: cover;">
                            </td>
                            ` : ''}
                            <td style="vertical-align: middle;">
                                <h1 style="font-size: 26pt; font-weight: 800; color: #ffffff; margin: 0 0 4px 0;">${data.personalInfo.fullName || 'John Doe'}</h1>
                                <h2 style="font-size: 12pt; font-weight: 600; color: ${primary}; margin: 0; text-transform: uppercase; letter-spacing: 0.05em;">${data.personalInfo.jobTitle || 'Lead Software Engineer'}</h2>
                            </td>
                            <td style="width: 40%; text-align: right; vertical-align: middle; font-size: 9pt; color: #94a3b8; line-height: 1.5;">
                                ${data.personalInfo.email ? `<div>Email: ${data.personalInfo.email}</div>` : ''}
                                ${data.personalInfo.phone ? `<div>Phone: ${data.personalInfo.phone}</div>` : ''}
                                ${data.personalInfo.address ? `<div>Loc: ${data.personalInfo.address}</div>` : ''}
                                ${data.personalInfo.portfolio ? `<div>Web: ${data.personalInfo.portfolio}</div>` : ''}
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- Summary -->
                ${data.personalInfo.summary ? `
                    <div style="margin-bottom: ${spacing};">
                        <p style="font-size: 9.5pt; color: #cbd5e1; margin: 0; text-align: justify; line-height: 1.5;">${data.personalInfo.summary}</p>
                    </div>
                ` : ''}

                <!-- Body columns -->
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <!-- Left column: Work Experience, Projects, Custom Sections -->
                        <td style="width: 63%; vertical-align: top; padding-right: 20px;">
                            ${renderWorkExperience(data.experience, spacing, primary, true)}
                            ${renderProjects(data.projects, spacing, primary, true)}
                            ${renderCustomSections(data.customSections, spacing, primary, true)}
                        </td>
                        <!-- Right column: Education, Skills, Certifications -->
                        <td style="width: 37%; vertical-align: top; border-left: 1px solid #334155; padding-left: 20px;">
                            ${renderEducation(data.education, spacing, primary, true)}
                            ${renderSkills(data.skills, spacing, primary, true)}
                            ${renderCertifications(data.certifications, spacing, primary, true)}
                        </td>
                    </tr>
                </table>
            </div>
        `;
    }
};

// Spacing size helper mapping
function getSpacingSize(spacing) {
    switch (spacing) {
        case 'compact': return '12px';
        case 'loose': return '28px';
        case 'comfortable':
        default:
            return '18px';
    }
}

// Work Experience rendering helper
function renderWorkExperience(experience, spacing, primary, dark = false) {
    if (!experience || experience.length === 0) return '';
    const textHeading = dark ? '#ffffff' : '#111827';
    const textBody = dark ? '#cbd5e1' : '#374151';
    const textMuted = dark ? '#94a3b8' : '#6b7280';
    const borderCol = dark ? '#334155' : primary;
    
    return `
        <div style="margin-bottom: ${spacing};">
            <div style="font-weight: bold; text-transform: uppercase; font-size: 10.5pt; color: ${primary}; border-bottom: 1px solid ${borderCol}; padding-bottom: 4px; margin-bottom: 12px; letter-spacing: 0.05em;">Experience</div>
            ${experience.map(exp => `
                <div style="margin-bottom: 12px;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                        <tr>
                            <td style="font-weight: bold; color: ${textHeading}; width: 70%; vertical-align: top;">${exp.role || 'Role'}</td>
                            <td style="text-align: right; font-style: italic; color: ${textMuted}; width: 30%; vertical-align: top;">${exp.startDate || ''} – ${exp.endDate || 'Present'}</td>
                        </tr>
                        <tr>
                            <td colspan="2" style="color: ${primary}; font-weight: 600; font-size: 9pt; padding-top: 2px;">${exp.company || 'Company'}</td>
                        </tr>
                    </table>
                    <p style="font-size: 9.5pt; margin: 4px 0 0 0; color: ${textBody}; white-space: pre-line; line-height: 1.4;">${exp.description || ''}</p>
                </div>
            `).join('')}
        </div>
    `;
}

// Projects rendering helper
function renderProjects(projects, spacing, primary, dark = false) {
    if (!projects || projects.length === 0) return '';
    const textHeading = dark ? '#ffffff' : '#111827';
    const textBody = dark ? '#cbd5e1' : '#374151';
    const textMuted = dark ? '#94a3b8' : '#6b7280';
    const borderCol = dark ? '#334155' : primary;

    return `
        <div style="margin-bottom: ${spacing};">
            <div style="font-weight: bold; text-transform: uppercase; font-size: 10.5pt; color: ${primary}; border-bottom: 1px solid ${borderCol}; padding-bottom: 4px; margin-bottom: 12px; letter-spacing: 0.05em;">Projects</div>
            ${projects.map(proj => `
                <div style="margin-bottom: 12px;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                        <tr>
                            <td style="font-weight: bold; color: ${textHeading}; width: 65%; vertical-align: top;">
                                ${proj.name || 'Project Name'}
                                ${proj.liveUrl ? ` <span style="font-weight: normal; font-size: 8.5pt;"><a href="${proj.liveUrl}" target="_blank" style="color: ${primary}; text-decoration: none;">[Link]</a></span>` : ''}
                            </td>
                    </table>
                    <p style="font-size: 9.5pt; margin: 4px 0 0 0; color: #374151; white-space: pre-line;">${proj.description || ''}</p>
                </div>
            `).join('')}
        </div>
    `;
}

// Education rendering helper
function renderEducation(education, spacing, primary) {
    if (!education || education.length === 0) return '';
    return `
        <div style="margin-bottom: ${spacing};">
            <div style="font-weight: bold; text-transform: uppercase; font-size: 11pt; color: ${primary}; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin-bottom: 12px;">Education</div>
            ${education.map(edu => `
                <div style="margin-bottom: 10px;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 9.5pt;">
                        <tr>
                            <td style="font-weight: bold; color: #111827;">${edu.degree || 'Degree'}</td>
                            <td style="text-align: right; font-style: italic; color: #6b7280;">${edu.startDate || ''} – ${edu.endDate || ''}</td>
                        </tr>
                        <tr>
                            <td colspan="2" style="color: #4b5563; font-style: italic; font-size: 9pt;">
                                ${edu.institution || ''} ${edu.grade ? `| Grade: ${edu.grade}` : ''}
                            </td>
                        </tr>
                    </table>
                </div>
            `).join('')}
        </div>
    `;
}

// Skills rendering helper
function renderSkills(skills, spacing, primary) {
    if (!skills || skills.length === 0) return '';
    return `
        <div style="margin-bottom: ${spacing};">
            <div style="font-weight: bold; text-transform: uppercase; font-size: 11pt; color: ${primary}; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin-bottom: 12px;">Skills</div>
            ${skills.map(s => `
                <div style="margin-bottom: 8px; font-size: 9.5pt;">
                    <strong style="color: #111827;">${s.name || ''}</strong>${s.tags && s.tags.length > 0 ? `: ${s.tags.join(', ')}` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

// Certifications rendering helper
function renderCertifications(certifications, spacing, primary) {
    if (!certifications || certifications.length === 0) return '';
    return `
        <div style="margin-bottom: ${spacing};">
            <div style="font-weight: bold; text-transform: uppercase; font-size: 11pt; color: ${primary}; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin-bottom: 12px;">Certifications</div>
            <ul style="margin: 0; padding-left: 16px; font-size: 9.5pt; color: #374151;">
                ${certifications.map(cert => `
                    <li style="margin-bottom: 4px;">${cert}</li>
                `).join('')}
            </ul>
        </div>
    `;
}

// Custom Sections rendering helper
function renderCustomSections(customSections, spacing, primary) {
    if (!customSections || customSections.length === 0) return '';
    return `
        ${customSections.map(sect => `
            <div style="margin-bottom: ${spacing};">
                <div style="font-weight: bold; text-transform: uppercase; font-size: 11pt; color: ${primary}; border-bottom: 1px solid ${primary}; padding-bottom: 4px; margin-bottom: 12px;">${sect.sectionTitle || 'Custom Section'}</div>
                <p style="font-size: 9.5pt; margin: 0; color: #374151; white-space: pre-line;">${sect.sectionContent || ''}</p>
            </div>
        `).join('')}
    `;
}

// The main template compiler called by builder UI
export function compileTemplate(templateId, data, style) {
    // Standardize input structures to prevent template mapping from throwing exceptions
    const normalizedData = {
        personalInfo: data?.personalInfo || {},
        experience: data?.experience || [],
        education: data?.education || [],
        skills: data?.skills || [],
        projects: data?.projects || [],
        certifications: data?.certifications || [],
        customSections: data?.customSections || []
    };
    
    const normalizedStyle = style || {
        primaryColor: '#EC5B38',
        fontFamily: 'Inter',
        spacing: 'comfortable',
        layout: 'two'
    };
    
    const templateFn = RESUME_TEMPLATES[templateId] || RESUME_TEMPLATES['modern_professional'];
    if (typeof templateFn === 'function') {
        return templateFn(normalizedData, normalizedStyle);
    }
    return '';
}

export { RESUME_TEMPLATES };

if (typeof window !== 'undefined') {
    window.RESUME_TEMPLATES = RESUME_TEMPLATES;
    window.compileTemplate = compileTemplate;
}