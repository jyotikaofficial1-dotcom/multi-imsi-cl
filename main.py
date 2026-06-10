import sys


def main():
    if "--cli" in sys.argv:
        _run_cli()
    else:
        _run_gui()


def _run_gui():
    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("Multi-IMSI Test Tool")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


def _run_cli():
    import argparse
    from transport.reader_manager import ReaderManager
    from transport.connection import CardConnection
    from engine.card_io import CardIO
    from security.adm_keys import ADMKeyManager
    from runner.registry import TestRegistry
    from runner.result import TestStatus
    from reports.html_report import HTMLReporter
    from reports.json_export import JSONExporter
    from getpass import getpass

    parser = argparse.ArgumentParser(description="Multi-IMSI CLI test runner")
    parser.add_argument("--all", action="store_true", help="Run all TCs")
    parser.add_argument("--ids", nargs="+", help="Specific TC IDs")
    parser.add_argument("--reader", type=int, default=0, help="Reader index")
    parser.add_argument("--out", default="report.html", help="HTML report path")
    parser.add_argument("--json", default="", help="JSON output path")
    parser.add_argument("--no-vault", action="store_true", help="Skip ADM vault")
    args = parser.parse_args()

    rm = ReaderManager()
    readers = rm.list_readers()
    if not readers:
        print("ERROR: No PC/SC readers found", file=sys.stderr)
        sys.exit(1)
    print(f"Using reader: {readers[args.reader]}")

    raw_conn = rm.connect(args.reader)
    conn = CardConnection(raw_conn)
    card = CardIO(conn)
    atr = rm.get_atr(raw_conn)
    print(f"ATR: {atr}")

    adm = None
    vault_path = "security/key_store.enc"
    if not args.no_vault:
        import os
        if os.path.exists(vault_path):
            passphrase = getpass("ADM vault passphrase: ").encode()
            try:
                adm = ADMKeyManager(vault_path, passphrase)
                adm.verify(card)
                print("ADM authentication: OK")
            except Exception as e:
                print(f"WARNING: ADM authentication failed: {e}", file=sys.stderr)
                adm = None
        else:
            print(f"WARNING: Vault not found at {vault_path}", file=sys.stderr)

    registry = TestRegistry()
    if args.all or args.ids is None:
        test_classes = list(registry._classes.values())
    else:
        test_classes = registry.get_selected(args.ids)

    print(f"\nRunning {len(test_classes)} test case(s)...\n")
    results = []
    for TestClass in sorted(test_classes, key=lambda c: c.TC_ID):
        tc = TestClass(card)
        print(f"  {tc.TC_ID}: {tc.TITLE} ... ", end="", flush=True)
        result = tc.execute()
        results.append(result)
        print(result.status.value)

    passed = sum(1 for r in results if r.status.value == "PASS")
    print(f"\nDone — {passed}/{len(results)} passed")

    HTMLReporter(results, atr).save(args.out)
    print(f"HTML report: {args.out}")

    if args.json:
        JSONExporter(results, atr).save(args.json)
        print(f"JSON report: {args.json}")

    conn.disconnect()
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    main()
