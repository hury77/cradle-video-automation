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
    global.chrome = { 
        runtime: { sendMessage: () => {}, getManifest: () => ({version: "1.0"}) },
        storage: { local: { get: (k, cb) => { if(cb) cb({}); }, set: () => {}, remove: () => {} } }
    };
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
    const row1 = document.querySelector("tr");
    const res1 = scanner1.extractEmissionFromRow(row1, 0);
    assertEqual("Test 1 (Zwykły ZIP obok tagu A)", res1?.name, "moj_wielki_plik.zip");

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
    const row2 = document.querySelector("tr");
    const res2 = scanner2.extractAcceptanceFromRow(row2, 0);
    assertEqual("Test 2 (nc-download z hintem)", res2?.name, "acceptance_video.mp4");

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
    const row3 = document.querySelector("tr");
    // W pm distribution zazwyczaj wyciągamy acceptance manualnie
    const res3 = scanner3.extractAcceptanceFromRow(row3, 0);
    assertEqual("Test 3 (URL fallback do .mp4)", res3?.name, "comments.mp4");

    // ---------------------------------------------------------
    // TEST 4: Chronologiczne sortowanie kandydatów - Scenariusz z 3 wpisami (najnowszy na końcu)
    // ---------------------------------------------------------
    const html4 = `
        <table>
            <tbody>
                <tr>
                    <td>broadcast file preparation<br>Action: accept (processing)</td>
                    <td>2026-09-02 12:27</td>
                    <td><a href="/media/cradle/comment/1/file_A.mp4"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>technical QA<br>Action: reject</td>
                    <td>2026-09-02 13:04</td>
                    <td><a href="/media/cradle/comment/2/screenshot.png"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>broadcast file preparation<br>Action: accept</td>
                    <td>2026-09-02 13:33</td>
                    <td><a href="/media/cradle/comment/3/file_B.mp4"><i class="fa-file"></i></a></td>
                </tr>
            </tbody>
        </table>
    `;
    const scanner4 = createMockScanner(html4);
    const table4 = document.querySelector("table");
    const result4 = scanner4.scanTableForFiles(table4);
    assertEqual("Test 4 (Chronologia: wybiera najnowszy wpis)", result4.emissionFile?.name, "file_B.mp4");

    // ---------------------------------------------------------
    // TEST 5: Chronologiczne sortowanie - Najnowszy jest REJECT, ale ma plik (ignoruje status)
    // ---------------------------------------------------------
    const html5 = `
        <table>
            <tbody>
                <tr>
                    <td>broadcast file preparation<br>Action: accept</td>
                    <td>2026-09-02 11:00</td>
                    <td><a href="/media/cradle/comment/1/old.mp4"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>broadcast file preparation<br>Action: reject</td>
                    <td>2026-09-02 14:00</td>
                    <td><a href="/media/cradle/comment/2/new_rejected_but_valid.mp4"><i class="fa-file"></i></a></td>
                </tr>
            </tbody>
        </table>
    `;
    const scanner5 = createMockScanner(html5);
    const table5 = document.querySelector("table");
    const result5 = scanner5.scanTableForFiles(table5);
    assertEqual("Test 5 (Najnowszy plik jest reject - ignoruje status)", result5.emissionFile?.name, "new_rejected_but_valid.mp4");

    // ---------------------------------------------------------
    // TEST 6: Sortowanie przy większej liczbie wpisów (reject -> accept -> reject -> accept) z najnowszym na szczycie
    // ---------------------------------------------------------
    const html6 = `
        <table>
            <tbody>
                <tr>
                    <td>final file preparation</td>
                    <td>2026-09-02 15:00</td>
                    <td><a href="/media/cradle/comment/4/v4.mp4"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>final file preparation</td>
                    <td>2026-09-02 14:00</td>
                    <td><a href="/media/cradle/comment/3/v3.mp4"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>final file preparation</td>
                    <td>2026-09-02 13:00</td>
                    <td><a href="/media/cradle/comment/2/v2.mp4"><i class="fa-file"></i></a></td>
                </tr>
                <tr>
                    <td>final file preparation</td>
                    <td>2026-09-02 12:00</td>
                    <td><a href="/media/cradle/comment/1/v1.mp4"><i class="fa-file"></i></a></td>
                </tr>
            </tbody>
        </table>
    `;
    const scanner6 = createMockScanner(html6);
    const table6 = document.querySelector("table");
    const result6 = scanner6.scanTableForFiles(table6);
    assertEqual("Test 6 (Sortowanie wielokrotne, najnowszy na szczycie HTML)", result6.emissionFile?.name, "v4.mp4");

    console.log(`\nWynik: ${passed} zdane, ${failed} oblane.`);
    if (failed > 0) process.exit(1);
}

runTests();
