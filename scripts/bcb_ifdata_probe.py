from __future__ import annotations

import json
from typing import Any

import httpx

BASE = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata"
ANO_MES = 202512


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
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        reports = _values(
            _get(client, "ListaDeRelatorio()", {"$format": "json"})
        )
        print(
            json.dumps(
                {"reports": reports},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

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
        itau = [
            row
            for row in cadastro
            if "ITAU" in str(row.get("NomeInstituicao") or "").upper()
            or "ITAÚ" in str(row.get("NomeInstituicao") or "").upper()
        ]
        print(json.dumps({"itau_candidates": itau}, ensure_ascii=False, sort_keys=True))
        if not itau:
            raise RuntimeError("no ITAU candidate found in IFDataCadastro")

        prudent_candidates = [
            row
            for row in itau
            if row.get("Situacao") == "A"
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

        report_rows: dict[str, list[dict[str, Any]]] = {}
        for report in reports:
            number = str(report.get("NumeroRelatorio") or "").strip()
            if not number:
                continue
            payload = _get(
                client,
                "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)",
                {
                    "@AnoMes": ANO_MES,
                    "@TipoInstituicao": 1,
                    "@Relatorio": f"'{number}'",
                    "$format": "json",
                    "$filter": f"CodInst eq '{cod_inst}'",
                    "$select": (
                        "TipoInstituicao,CodInst,AnoMes,NomeRelatorio,NumeroRelatorio,"
                        "Grupo,Conta,NomeColuna,DescricaoColuna,Saldo"
                    ),
                },
            )
            rows = _values(payload)
            if rows:
                report_rows[number] = rows
        print(
            json.dumps(
                {"report_rows": report_rows},
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
