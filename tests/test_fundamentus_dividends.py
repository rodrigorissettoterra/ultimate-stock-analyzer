from ultimate_stock_analyzer.collectors.fundamentus import FundamentusDividendCollector


def test_parse_fundamentus_dividend_table() -> None:
    html = """
    <table>
      <thead><tr><th>Data</th><th>Valor</th><th>Tipo</th><th>Data de Pagamento</th><th>Por quantas ações</th></tr></thead>
      <tbody>
        <tr><td>31/07/2026</td><td>0,0182</td><td>JRS CAP PROPRIO</td><td>01/09/2026</td><td>1</td></tr>
        <tr><td>09/12/2025</td><td>1,8682</td><td>DIVIDENDO</td><td>19/12/2025</td><td>1</td></tr>
      </tbody>
    </table>
    """
    payments = FundamentusDividendCollector.parse_html(html)
    assert len(payments) == 2
    assert payments[0].kind == "DIVIDEND"
    assert payments[1].kind == "JCP"
    assert payments[1].amount_per_share == 0.0182
