## Design Context

### Users
- **Primary**: Faculty/staff and students in an internal network environment
- **Context**: Searching for school announcements, regulations, and official documents
- **Job to be done**: Users arrive with a specific question and need to find the answer fast — the interface must communicate credibility, intelligence, and speed
- **Devices**: Desktop (office) and mobile (on-the-go) both common — students frequently use phones; design must work excellently on both, not just responsive-at-the-end

### Brand Personality
- **Voice**: Precise, direct, no-nonsense. Information first.
- **Tone**: Modern technical tool — like a well-engineered developer tool or an enterprise-grade search product
- **3-word personality**: Modern · Tech · Clear
- **Emotional goal**: Users should feel "this is a smart, reliable system built for me" — not a generic portal

### Aesthetic Direction
- **Visual tone**: Sharp editorial meets precision instrument. Think Linear's clean density combined with Bloomberg Terminal's confidence. Information-dense but never cluttered.
- **Theme**: Both light and dark, user-controlled with auto-detection fallback
- **Color strategy**: For light mode — cool gray/slate base with a strong, confident accent (NOT purple-to-blue gradient, NOT cyan-on-dark). For dark mode — same slate base, deeper tones, no neon glow. The tech feel comes from **precision**, not decoration.
- **Typography direction**: Distinctive display font for headings (NOT Syne, NOT Inter, NOT Fraunces) paired with a refined readable body font. The display font should feel like a product built by engineers who care about design.
- **Motion**: Purposeful and quick — no bounce, no elastic. Smooth deceleration only.
- **Anti-references**: Generic admin dashboards with left-border accent stripes, gradient hero sections, rounded card grids with centered icon+title+text, modals used as navigation, light-on-dark with cyan/blue neon glows

### Design Principles
1. **Speed is the primary emotion** — every visual choice reinforces "I will find what I need fast"
2. **Clarity over decoration** — every element earns its place; no visual noise
3. **Functional density** — information is prominent; whitespace is intentional, not filling space
4. **Light theme is the default** (office/desktop context), dark theme is a first-class citizen
5. **Typography creates hierarchy** — the type scale carries the design; don't rely on color to create hierarchy

### Homepage Design (Chat as Dashboard)

**Layout**: Chat-tool style — left sidebar for session history, main area is the conversation. When no session is active or it's a new session, the main area shows a dashboard with information cards instead of an empty state.

**Dashboard content (visible when chat is empty/new)**:
1. **最近通知** — Recent school announcements/docs list, fetched from `/api/search/recent`
2. **快捷提问** — Clickable example question cards that auto-fill and send, e.g. "食堂营业时间"、"奖学金申请流程"、"考试安排"
3. **个人统计** — User's question count, points balance, usage summary
4. **校园动态** — Latest school activities or important date reminders

**Style**: Same conversation-tool aesthetic — clean, dense, functional. Dashboard cards integrate into the chat flow naturally. When user sends a message, dashboard content scrolls up as context and conversation begins.

**First impression**: "A smart, capable assistant that already knows what's happening on campus" — not a blank input box.
