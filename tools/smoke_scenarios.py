"""Exercise shipped gameplay fixes using a private temporary profile and clock.

Checks use explicit exceptions: PyInstaller optimizes assert statements away.
No clock multiplier or test money is exposed to ordinary gameplay.
"""

from copy import deepcopy
import json
from pathlib import Path
import tempfile

from game.engine import Farm, PendingSaveError
from game.persistence import SaveStatus
from game.storage import RecoveryRequired, SaveStore
from tools.simulation import VirtualClock, earn_to
from ui.plot_tools import ReplantDialog
from ui.recovery import RecoveryDialog


def require(condition, message):
    if not condition:
        raise RuntimeError("Verificação do executável: " + message)


def check_features():
    with tempfile.TemporaryDirectory(prefix="idlefarm-shipped-checks-") as directory:
        root = Path(directory)
        clock = VirtualClock()
        farm = Farm(SaveStore(root / "features.json"), clock)
        farm.plant(0, "wheat")
        require(farm.remaining(0) == 60, "tutorial de 60 segundos ausente")
        clock.skip(60)
        farm.harvest(0)
        require(farm.tutorial_phase == "completed", "tutorial não concluído")
        farm = Farm(farm.store, clock)
        farm.plant(0, "wheat")
        require(farm.remaining(0) == 3600, "tutorial reaplicado após reabertura")
        clock.skip(3600)
        farm.harvest_ready()
        before = farm.state["coins"]
        proposal = ReplantDialog(farm, "wheat")
        require(
            proposal.quantity.value() == 2 and proposal.confirm.isEnabled(), "confirmação em lote ausente"
        )
        proposal.accept()
        require(proposal.selection == ("wheat", (0, 1)), "proposta de plantio inválida")
        planted = farm.plant_batch(*proposal.selection)
        require(planted["count"] == 2 and farm.state["coins"] == before - 10, "plantio em lote incorreto")
        clock.skip(3600)
        harvested = farm.harvest_ready()
        require(harvested["count"] == 2 and harvested["reward"] == 40, "colheita em lote incorreta")
        earn_to(farm, clock, 400)
        farm.construct("coop")
        before = farm.state["coins"]
        price = farm.animal_price("chicken")
        save = farm.store.save

        def write_failure(snapshot):
            raise OSError("falha de gravação simulada em perfil de QA")

        farm.store.save = write_failure
        try:
            try:
                farm.buy_animal("chicken")
            except PendingSaveError:
                pass
            else:
                raise RuntimeError("A falha simulada de gravação não foi detectada")
            require(farm.count("chicken") == 1, "compra pendente descartada")
            require(farm.persistence.status == SaveStatus.ERROR, "falha apresentada como sucesso")
            clock.skip(1800)
            farm.advance()
        finally:
            farm.store.save = save
        farm.save()
        farm = Farm(farm.store, clock)
        require(farm.state["coins"] == before - price + 15, "cobrança ou produção repetida na tentativa")
        require(farm.count("chicken") == 1 and farm.offline_reward == 0, "compra duplicada")

        original = deepcopy(farm.state)
        live_store, closed_store = SaveStore(root / "live.json"), SaveStore(root / "closed.json")
        live_store.save(original)
        closed_store.save(original)
        live = Farm(live_store, clock)
        clock.skip(8 * 3600)
        live_gain = live.advance()
        reopened = Farm(closed_store, clock)
        require(live_gain == reopened.offline_reward == 120, "suspensão difere da reabertura")
        require(live.state == reopened.state, "estado temporal divergente")
        live.save()
        require(Farm(live_store, clock).offline_reward == 0, "ausência contabilizada duas vezes")

        recover = SaveStore(root / "recovery.json")
        damaged = deepcopy(live.state)
        damaged["last_accounted"] = 10**1000
        recover.path.write_text(json.dumps(damaged), encoding="utf-8")
        recover.backup.write_text(json.dumps(live.state), encoding="utf-8")
        bad_bytes, good_bytes = recover.path.read_bytes(), recover.backup.read_bytes()
        try:
            recover.load()
        except RecoveryRequired as error:
            require(error.backup_data is not None, "backup válido não encontrado")
            recovery_dialog = RecoveryDialog(recover, error, clock=clock)
            require(recovery_dialog.restore_button.isEnabled(), "restauração válida indisponível")
            recovery_dialog.reject()
        else:
            raise RuntimeError("Timestamp inválido aceito pelo executável")
        require(
            recover.path.read_bytes() == bad_bytes and recover.backup.read_bytes() == good_bytes,
            "diagnóstico alterou o progresso",
        )
        # A QA action explicitly exercises the same consent-gated restore API;
        # no player profile is involved in this private temporary directory.
        recover.restore_backup()
        require(
            any(p.read_bytes() == bad_bytes for p in root.glob("*.corrupt-*")),
            "original inválido não foi preservado",
        )
        require(json.loads(recover.path.read_text()) == live.state, "backup restaurado incorretamente")
        legacy = deepcopy(live.state)
        legacy.pop("tutorial", None)
        legacy_store = SaveStore(root / "legacy.json")
        legacy_store.save(legacy)
        loaded = Farm(legacy_store, clock)
        require(
            loaded.state == legacy and loaded.planting_seconds("wheat") == 3600,
            "progresso antigo alterado pelo tutorial",
        )
        return {
            "tutorial_seconds": 60,
            "normal_wheat_seconds": 3600,
            "batch_operations": True,
            "batch_confirmation_dialog": True,
            "recovery_dialog_cancel": True,
            "pending_purchase_retry_once": True,
            "recovery_preserves_files": True,
            "resume_matches_reopen": True,
            "legacy_save_compatible": True,
        }
