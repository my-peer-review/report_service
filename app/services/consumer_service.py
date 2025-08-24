# app/report_consumer.py
import asyncio
from datetime import datetime
import json
import logging
from typing import Optional, Callable, Awaitable
import aio_pika
from aio_pika import ExchangeType, IncomingMessage

from app.database.report_repository import ReportRepository 

logger = logging.getLogger(__name__)

class ReportConsumerService:
    """
    Consumatore multiplo per:
      - assignments.report
      - submissions.report
      - review.reports
    Tutte le code condividono lo stesso exchange DIRECT.
    """

    def __init__(
        self,
        repo: ReportRepository,
        rabbitmq_url: str,
        *,
        exchange_name: str = "elearning.reports",
        heartbeat: int = 30,
        durable: bool = True,
        prefetch_count: int = 20,
        requeue_on_error: bool = False,
    ) -> None:
        self.repo = repo
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.heartbeat = heartbeat
        self.durable = durable
        self.prefetch_count = prefetch_count
        self.requeue_on_error = requeue_on_error

        # risorse AMQP
        self._conn: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

        # consumer tags per poter fare cancel pulito
        self._consumer_tags: list[str] = []

        # lock per operazioni critiche (close/ensure)
        self._lock = asyncio.Lock()

        # code/routing keys (qui rk == queue name per semplicità)
        self.assignments_q = "assignments.reports"
        self.submissions_q = "submissions.reports"
        self.reviews_q = "reviews.reports"

    # -----------------------------
    # Lifecycle
    # -----------------------------
    async def connect(self, max_retries: int = 5, delay: int = 3) -> None:
        """Apre connessione e dichiara exchange con retry/backoff."""
        attempt = 0
        while True:
            try:
                logger.debug("Tentativo connessione RabbitMQ #%s", attempt + 1)
                self._conn = await aio_pika.connect_robust(
                    self.rabbitmq_url,
                    heartbeat=self.heartbeat,
                )
                # publisher_confirms=True: utile anche se qui consumiamo soltanto,
                # mantiene coerenza con il tuo stile.
                self._channel = await self._conn.channel(publisher_confirms=True)
                await self._channel.set_qos(prefetch_count=self.prefetch_count)

                self._exchange = await self._channel.declare_exchange(
                    self.exchange_name, ExchangeType.DIRECT, durable=self.durable
                )

                logger.info("Connessione a RabbitMQ stabilita.")
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                logger.warning("Connessione fallita: %s", exc)
                if attempt >= max_retries:
                    logger.error(
                        "Impossibile connettersi a RabbitMQ dopo %s tentativi.", max_retries
                    )
                    raise
                await asyncio.sleep(delay)

    async def _ensure_ready(self) -> None:
        """Garantisce che connessione, canale ed exchange siano pronti."""
        async with self._lock:
            if not self._conn or self._conn.is_closed:
                logger.debug("Connessione non attiva: provo a riconnettermi.")
                await self.connect()

            if not self._channel or self._channel.is_closed:
                logger.debug("Canale non attivo: riapro il canale.")
                assert self._conn is not None
                self._channel = await self._conn.channel(publisher_confirms=True)
                await self._channel.set_qos(prefetch_count=self.prefetch_count)

            if not self._exchange:
                logger.debug("Exchange non presente in cache: lo dichiaro/recupero.")
                assert self._channel is not None
                self._exchange = await self._channel.declare_exchange(
                    self.exchange_name, ExchangeType.DIRECT, durable=self.durable
                )

    async def close(self) -> None:
        """Chiude in modo pulito consumer, canale e connessione."""
        async with self._lock:
            # cancella i consumer se presenti
            if self._channel and not self._channel.is_closed and self._consumer_tags:
                try:
                    for tag in self._consumer_tags:
                        try:
                            await self._channel.basic_cancel(tag)
                        except Exception:
                            logger.exception("Errore durante cancel consumer tag=%s", tag)
                finally:
                    self._consumer_tags.clear()

            # chiudi canale e connessione
            try:
                if self._channel and not self._channel.is_closed:
                    logger.debug("Chiusura canale RabbitMQ.")
                    await self._channel.close()
            finally:
                if self._conn and not self._conn.is_closed:
                    logger.debug("Chiusura connessione RabbitMQ.")
                    await self._conn.close()

            # reset
            self._conn = None
            self._channel = None
            self._exchange = None

    def is_ready(self) -> bool:
        return bool(
            self._conn
            and not self._conn.is_closed
            and self._channel
            and not self._channel.is_closed
            and self._exchange
        )

    # -----------------------------
    # Consumo
    # -----------------------------
    async def start(self) -> None:
        """Avvia la connessione e si mette in ascolto sulle 3 queue."""
        await self._ensure_ready()
        await self._declare_and_consume(self.assignments_q, self._on_assignment_message)
        await self._declare_and_consume(self.submissions_q, self._on_submission_message)
        await self._declare_and_consume(self.reviews_q, self._on_review_message)
        logger.info("ReportConsumerService avviato e in ascolto su 3 code.")

    async def stop(self) -> None:
        await self.close()
        logger.info("ReportConsumerService arrestato.")

    async def _declare_and_consume(
        self,
        queue_name: str,
        handler: Callable[[IncomingMessage], Awaitable[None]],
    ) -> None:
        """Dichiara queue, bind a exchange e attiva il consumer con callback dedicata."""
        assert self._channel is not None and self._exchange is not None

        queue = await self._channel.declare_queue(
            name=queue_name,
            durable=self.durable,
            exclusive=False,
            auto_delete=False,
        )
        await queue.bind(self._exchange, routing_key=queue_name)

        tag = await queue.consume(handler, no_ack=False)
        self._consumer_tags.append(tag)
        logger.info("Queue pronta: %s (consumer tag=%s)", queue_name, tag)

    # -----------------------------
    # Handlers messaggi
    # -----------------------------
    async def _on_assignment_message(self, message: IncomingMessage) -> None:
        try:
            body = message.body.decode("utf-8")
            payload = json.loads(body)

            # Estrazione campi richiesti
            assignment_id = payload.get("assignmentId")
            status        = payload.get("status")
            teacher_id    = payload.get("teacherId")

            # Validazione minima
            if not assignment_id:
                raise ValueError("Missing required field: assignmentId")
            if not status:
                raise ValueError("Missing required field: status")

            # Upsert stato assignment
            await self.repo.insert_assignment_event(
                assignment_id=assignment_id,
                status=status,
            )

            if status == "open":
                await self.repo.insert_teacher_assignment(
                    assignment_id=assignment_id,
                    teacher_id=teacher_id,
                )

            await message.ack()
            logger.info("Assignment processed",
                        extra={"assignmentId": assignment_id, "status": status, "teacherId": teacher_id})

        except json.JSONDecodeError:
            logger.exception("JSON assignments non valido: decode fallita")
            await message.nack(requeue=self.requeue_on_error)

        except ValueError as ve:
            logger.error("Validation error su assignments: message rejected (no requeue)",
                         extra={"error": str(ve)})
            await message.nack(requeue=False)

        except Exception:
            logger.exception("Errore processamento assignments (DB/altro)")
            await message.nack(requeue=self.requeue_on_error)

    # -----------------------------
    # submissions.report
    # -----------------------------
    async def _on_submission_message(self, message: IncomingMessage) -> None:
        try:
            body = message.body.decode("utf-8")
            payload = json.loads(body)

            # payload atteso: { assignmentId, submissionId, studentId, deliveredAt }
            assignment_id = payload.get("assignmentId")
            submission_id = payload.get("submissionId")
            student_id    = payload.get("studentId")
            raw =           payload.get("deliveredAt")

            delivered_at = datetime.fromisoformat(raw)

            logger.info("Uso di 'submissiontId' (typo) accettato",
                extra={"assignmentId": assignment_id, "submissionId": submission_id})

            # Validazione minima
            if not assignment_id:
                raise ValueError("Missing required field: assignmentId")
            if not submission_id:
                raise ValueError("Missing required field: submissionId")
            if not student_id:
                raise ValueError("Missing required field: studentId")
            if not delivered_at:
                raise ValueError("Missing/invalid required field: deliveredAt (ISO datetime)")

            await self.repo.insert_submission_event(
                assignment_id=assignment_id,
                submission_id=submission_id,
                student_id=student_id,
                delivered_at=delivered_at,
            )

            await message.ack()
            logger.info("Submission processed",
                        extra={"assignmentId": assignment_id, "submissionId": submission_id,
                            "studentId": student_id, "deliveredAt": delivered_at.isoformat()})

        except json.JSONDecodeError:
            logger.exception("JSON submissions non valido")
            await message.nack(requeue=self.requeue_on_error)
        except ValueError as ve:
            logger.error("Validation error su submissions: message rejected (no requeue)",
                        extra={"error": str(ve)})
            await message.nack(requeue=False)
        except Exception:
            logger.exception("Errore processamento submissions")
            await message.nack(requeue=self.requeue_on_error)

    # -----------------------------
    # review.reports
    # -----------------------------
    async def _on_review_message(self, message: IncomingMessage) -> None:
        try:
            body = message.body.decode("utf-8")
            payload = json.loads(body)

            # payload atteso: { submissionId, punteggio }
            submission_id = payload.get("submissionId")
            review_id     = payload.get("reviewId")
            punteggio     = payload.get("punteggio")
            raw = payload.get("deliveredAt")

            delivered_at = datetime.fromisoformat(raw)

            # Validazione minima
            if not submission_id:
                raise ValueError("Missing required field: submissionId")
            if punteggio is None:
                raise ValueError("Missing required field: punteggio")

            await self.repo.insert_review_event(
                submission_id=submission_id,
                review_id=review_id,
                punteggio=int(punteggio),
                delivered_at = delivered_at
            )

            await message.ack()
            logger.info("Review processed",
                        extra={"submissionId": submission_id, "punteggio": int(punteggio)})

        except json.JSONDecodeError:
            logger.exception("JSON review non valido")
            await message.nack(requeue=self.requeue_on_error)

        except ValueError as ve:
            logger.error("Validation error su review: message rejected (no requeue)",
                         extra={"error": str(ve)})
            await message.nack(requeue=False)

        except Exception:
            logger.exception("Errore processamento review")
            await message.nack(requeue=self.requeue_on_error)