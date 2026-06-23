const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

// Wczytaj plik cradle-scanner.js jako string
const scannerCode = fs.readFileSync(path.join(__dirname, "../content/cradle-scanner.js"), "utf8");

function createMockScanner(html) {
    const dom = new JSDOM(`<!DOCTYPE html><body>${html}</body>`);
    const { window } = dom;
    
    // Mock global variables expected by cradle-scanner.js
    global.document = window.document;
    global.window = window;
    global.navigator = { userAgent: "node" };
    global.chrome = { runtime: { sendMessage: () => {}, getManifest: () => ({version: "1.0"}) } };
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.location = { href: "https://cradle.egplusww.pl/asset/123", search: "?id=123" };
    
    // Evaluate the scanner code in this context
    // Omijamy wywołania constructor logic i auto-start poprzez proste eval class
    const script = `
        ${scannerCode.replace(/const scanner = new CradleScanner\(\);/g, "")}
        module.exports = CradleScanner;
    `;
    
    const Module = module.constructor;
    const m = new Module();
    m._compile(script, "cradle-scanner-mock.js");
    const CradleScanner = m.exports;
    
    return new CradleScanner();
}

async function runTests() {
    console.log("🚀 Uruchamianie testów DOM dla CradleScanner...");
    let passed = 0;
    let failed = 0;

    function assertEqual(testName, actual, expected) {
        if (actual === expected) {
            console.log(`✅ TEST PASSED: ${testName}`);
            passed++;
        } else {
            console.error(`❌ TEST FAILED: ${testName}`);
            console.error(`   Oczekiwano: ${expected}`);
            console.error(`   Otrzymano:  ${actual}`);
            failed++;
        }
    }

    // ---------------------------------------------------------
    // TEST 1: Klasyczny załącznik z rozszerzeniem obok ikonki
    // ---------------------------------------------------------
    const html1 = `
        <table>
            <tr>
                <td>broadcast file preparation</td>
                <td>
                    <a href="/media/cradle/comment/1111/download">
                        <i class="fa-file"></i>
                    </a>
                    moj_wielki_plik.zip
                </td>
            </tr>
        </table>
    `;
    const scanner1 = createMockScanner(html1);
    const fileInfo1 = {};
    const row1 = document.querySelector("tr");
    scanner1.extractEmissionFromRow(row1, fileInfo1, 0);
    assertEqual("Test 1 (Zwykły ZIP obok tagu A)", fileInfo1.emissionFile?.name, "moj_wielki_plik.zip");

    // ---------------------------------------------------------
    // TEST 2: plik z bezpośrednim wpisem nc-download z hintem
    // ---------------------------------------------------------
    const html2 = `
        <table>
            <tr>
                <td>video preparation</td>
                <td>
                    <a href="https://cradle.egplusww.pl/nc-download/somehash" title="acceptance_video.mp4">
                        <i class="fa-file"></i> Download
                    </a>
                </td>
            </tr>
        </table>
    `;
    const scanner2 = createMockScanner(html2);
    const fileInfo2 = {};
    const row2 = document.querySelector("tr");
    scanner2.extractAcceptanceFromRow(row2, fileInfo2, 0);
    assertEqual("Test 2 (nc-download z hintem)", fileInfo2.acceptanceFile?.name, "acceptance_video.mp4");

    // ---------------------------------------------------------
    // TEST 3: Link do pobrania bez rozszerzenia (np. pm distribution)
    // ---------------------------------------------------------
    const html3 = `
        <table>
            <tr>
                <td>video preparation</td>
                <td>
                    Prośba o final files z <br>
                    <a href="/media/cradle/comment/123/comments">
                        <i class="fa-file"></i>
                    </a>
                </td>
            </tr>
        </table>
    `;
    const scanner3 = createMockScanner(html3);
    const fileInfo3 = {};
    const row3 = document.querySelector("tr");
    // W pm distribution zazwyczaj wyciągamy acceptance manualnie
    scanner3.extractAcceptanceFromRow(row3, fileInfo3, 0);
    assertEqual("Test 3 (URL fallback do .mp4)", fileInfo3.acceptanceFile?.name, "comments.mp4");

    console.log(`\nWynik: ${passed} zdane, ${failed} oblane.`);
    if (failed > 0) process.exit(1);
}

runTests();
