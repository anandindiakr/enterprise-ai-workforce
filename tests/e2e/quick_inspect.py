from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto("http://localhost:4000/chat")
    page.wait_for_load_state("networkidle")

    inp = page.locator("textarea, input[type='text']").first
    print("INPUT VISIBLE:", inp.is_visible())
    inp.fill("Hello")
    inp.press("Enter")
    print("Sent. Waiting 4s...")
    page.wait_for_timeout(4000)

    # Dump all meaningful text elements
    all_els = page.evaluate("""() => {
        const result = [];
        document.querySelectorAll("div,p,span,li").forEach(el => {
            const t = (el.innerText || "").trim();
            if (t && t.length > 5 && t.length < 300) {
                result.push({
                    tag: el.tagName,
                    cls: (el.className || "").slice(0, 80),
                    text: t.slice(0, 120)
                });
            }
        });
        return result.slice(0, 40);
    }""")
    for el in all_els:
        print(f"  {el['tag']} cls={el['cls']}: {el['text']}")

    # Check if textarea is still there
    inputs = page.query_selector_all("textarea, input[type='text']")
    print(f"\nINPUTS AFTER SEND: {len(inputs)}")
    for i in inputs:
        print(f"  visible={i.is_visible()} val={repr(i.input_value()[:30])}")

    ctx.close()
    b.close()
