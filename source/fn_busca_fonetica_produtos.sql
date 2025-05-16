
-- DROP TYPES (se existirem)
BEGIN
  EXECUTE IMMEDIATE 'DROP TYPE produto_resultado_tab';
  EXECUTE IMMEDIATE 'DROP TYPE produto_resultado';
EXCEPTION
  WHEN OTHERS THEN NULL;
END;
/

-- Criação de um tipo de tabela para retorno da função
CREATE OR REPLACE TYPE produto_resultado AS OBJECT (
    codigo VARCHAR2(50),
    descricao VARCHAR2(4000),
    similaridade NUMBER
);

CREATE OR REPLACE TYPE produto_resultado_tab AS TABLE OF produto_resultado;
/

-- Função de busca fonética e por palavras-chave
CREATE OR REPLACE FUNCTION fn_busca_avancada(p_termos IN VARCHAR2)
RETURN produto_resultado_tab PIPELINED
AS
    v_termos SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST();
    v_token VARCHAR2(1000);
    v_descricao VARCHAR2(4000);
    v_score NUMBER;
    v_dummy NUMBER;
BEGIN
    -- Dividir os termos da busca
    FOR i IN 1..REGEXP_COUNT(p_termos, '\S+') LOOP
        v_termos.EXTEND;
        v_termos(i) := LOWER(REGEXP_SUBSTR(p_termos, '\S+', 1, i));
    END LOOP;

    -- Loop pelos produtos
    FOR prod IN (SELECT codigo, descricao FROM produtos) LOOP
        v_descricao := LOWER(prod.descricao);
        v_score := 0;

        -- Avaliar cada termo da busca
        FOR i IN 1..v_termos.COUNT LOOP
            v_token := v_termos(i);

            -- 3 pontos se encontrar diretamente
            IF v_descricao LIKE '%' || v_token || '%' THEN
                v_score := v_score + 3;
            ELSE
                -- 2 pontos se foneticamente similar
                BEGIN
                    SELECT 1 INTO v_dummy FROM dual
                    WHERE SOUNDEX(v_token) IN (
                        SELECT SOUNDEX(REGEXP_SUBSTR(v_descricao, '\w+', 1, LEVEL))
                        FROM dual
                        CONNECT BY LEVEL <= REGEXP_COUNT(v_descricao, '\w+')
                    );
                    v_score := v_score + 2;
                EXCEPTION
                    WHEN NO_DATA_FOUND THEN NULL;
                END;

                -- 1 ponto se similar por escrita
                BEGIN
                    SELECT 1 INTO v_dummy FROM dual
                    WHERE EXISTS (
                        SELECT 1
                        FROM (
                            SELECT REGEXP_SUBSTR(v_descricao, '\w+', 1, LEVEL) AS palavra
                            FROM dual
                            CONNECT BY LEVEL <= REGEXP_COUNT(v_descricao, '\w+')
                        )
                        WHERE UTL_MATCH.EDIT_DISTANCE(palavra, v_token) <= 2
                    );
                    v_score := v_score + 1;
                EXCEPTION
                    WHEN NO_DATA_FOUND THEN NULL;
                END;
            END IF;
        END LOOP;

        -- Só retorna se houver ao menos algum match
        IF v_score > 0 THEN
            PIPE ROW(produto_resultado(prod.codigo, prod.descricao, v_score));
        END IF;
    END LOOP;

    RETURN;
END;
/

-- Grant para execução, se necessário:
GRANT EXECUTE ON fn_busca_fonetica_por_palavra TO PUBLIC;


-- Testes
SELECT *
FROM TABLE(fn_busca_avancada('harry poter pedra'))
ORDER BY similaridade DESC;

SELECT * FROM TABLE(fn_busca_fonetica_por_palavra('velho mar'))
ORDER BY similaridade DESC;

    