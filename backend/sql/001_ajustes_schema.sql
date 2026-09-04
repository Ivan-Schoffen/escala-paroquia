-- Ajustes no schema existente.
-- Rodar UMA VEZ no SQL Editor do Supabase (New query > colar > Run).
-- Tudo aqui e idempotente: rodar de novo nao quebra nada.

-- 1. Qual vaga cada acolito preenche na celebracao.
--    Sem isso nao da para agrupar a escala por funcao nem validar o molde de vagas.
ALTER TABLE public.escala_acolitos
    ADD COLUMN IF NOT EXISTS funcao VARCHAR(20)
    CHECK (funcao IN ('Responsavel', 'Maior', 'Menor'));

-- 2. A mesma pessoa nao pode ocupar duas vagas na mesma celebracao.
CREATE UNIQUE INDEX IF NOT EXISTS uq_escala_acolito
    ON public.escala_acolitos (escala_id, acolito_id);

-- 3. Nome da solenidade, quando a celebracao vem do calendario de excecoes.
--    O tempo_liturgico sozinho nao cobre "Missa da Padroeira".
ALTER TABLE public.escalas_geradas
    ADD COLUMN IF NOT EXISTS titulo_evento VARCHAR(150);

-- 4. Gerar a escala duas vezes nao pode duplicar celebracoes.
CREATE UNIQUE INDEX IF NOT EXISTS uq_escala_igreja_datahora
    ON public.escalas_geradas (igreja_id, data_hora);

-- 5. Desativar sem apagar: preserva o historico das escalas ja publicadas.
ALTER TABLE public.missas_padrao
    ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE public.acolitos
    ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;

-- 6. Indices para o contador de balanceamento (RN01), que filtra
--    exatamente por essas duas colunas a cada geracao de escala.
CREATE INDEX IF NOT EXISTS idx_escala_acolitos_acolito
    ON public.escala_acolitos (acolito_id);

CREATE INDEX IF NOT EXISTS idx_escalas_geradas_mes_ano
    ON public.escalas_geradas (mes_ano_referencia);