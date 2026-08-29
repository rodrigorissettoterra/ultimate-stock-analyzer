from __future__ import annotations

import json
from typing import Any

import httpx

BASE = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata"
ANO_MES = 202512
REPORTS_TO_INSPECT = ("1", "2", "3", "4", "5")


def _get(client: httpx.Client, path: str, params: dict[str, object]) -> dict[str, Any]:
    response = client.get(f"{BASE}/{path}", params=params)
    print(json.dumps({"url": str(response.url), "status": response.status_code}))
    if response.status_code >= 400:
        print(json.dumps({"error_body": response.text[:1000]}, ensure_ascii=False))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("IFData response must be an object")
    return payload


def _values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("value")
    if not isinstance(rows, list):
        raise TypeError("IFData response has no value list")
    return [dict(row) for row in rows if isinstance(row, dict)]


def main() -> None:
    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        reports = _values(_get(client, "ListaDeRelatorio()", {"$format": "json"}))
        print(json.dumps({"reports": reports}, ensure_ascii=False, sort_keys=True))

        cadastro = _values(
            _get(
                client,
                "IfDataCadastro(AnoMes=@AnoMes)",
                {
                    "@AnoMes": ANO_MES,
                    "$format": "json",
                    "$select": (
                        "CodInst,Data,NomeInstituicao,Tcb,Td,Tc,SegmentoTb,Atividade,"
                        "Sr,CodConglomeradoFinanceiro,CodConglomeradoPrudencial,"
                        "CnpjInstituicaoLider,Situacao"
                    ),
                },
            )
        )
        prudent_candidates = [
            row
            for row in cadastro
            if row.get("Situacao") == "A"
            and row.get("CnpjInstituicaoLider") == "60872504"
            and row.get("CodConglomeradoPrudencial")
            and row.get("CodInst") == row.get("CodConglomeradoPrudencial")
        ]
        if len(prudent_candidates) != 1:
            raise RuntimeError(
                "expected exactly one ITAU prudential-conglomerate row, "
                f"found {len(prudent_candidates)}"
            )
        chosen = prudent_candidates[0]
        cod_inst = str(chosen["CodInst"])
        print(json.dumps({"chosen_cod_inst": cod_inst, "chosen": chosen}, ensure_ascii=False))

        report_names = {
            str(row.get("NumeroRelatorio")): str(row.get("NomeRelatorio"))
            for row in reports
        }
        target_reports: dict[str, dict[str, Any]] = {}
        for number in REPORTS_TO_INSPECT:
            payload = _get(
                client,
                "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)",
                {
                    "@AnoMes": ANO_MES,
                    "@TipoInstituicao": 1,
                    "@Relatorio": f"'{number}'",
                    "$format": "json",
                    "$select": (
                        "TipoInstituicao,CodInst,AnoMes,NomeRelatorio,NumeroRelatorio,"
                        "Grupo,Conta,NomeColuna,DescricaoColuna,Saldo"
                    ),
                },
            )
            rows = _values(payload)
            target_rows = [row for row in rows if str(row.get("CodInst")) == cod_inst]
            target_reports[number] = {
                "report_name": report_names.get(number),
                "all_rows": len(rows),
                "target_rows": len(target_rows),
                "columns": sorted({str(row.get("NomeColuna")) for row in target_rows}),
                "rows": target_rows,
            }
        print(
            json.dumps(
                {"target_reports": target_reports},
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
