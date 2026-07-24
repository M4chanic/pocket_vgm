// OKI MSM6258 (ADPCM-декодер X68000) — Verilog-порт e6258.vhd/calcadpcm.vhd
// из X68000_MiSTer (https://github.com/MiSTer-devel/X68000_MiSTer,
// rtl/sound/adpcm6258, автор оригинала puu, доработки MiSTer-devel).
// Поведение декодера сохранено 1:1 (таблица шагов, усечённые сдвиги дельты,
// рамп в тишину при пустом буфере и при остановке); интерфейс упрощён под
// один клоковый домен chipbox: записи латчатся до ближайшего cen.
//
// Регистры (addr): 0 — управление (бит 0 стоп, бит 1 воспроизведение),
// 1 — байт данных ADPCM (два нибла, младший первым).
// clkdiv: 00 -> /1024, 01 -> /768, 10/11 -> /512 от клока чипа (cen).
// drq — запрос следующего байта (аналог DMA-запроса X68000).

module msm6258 (
    input wire clk,
    input wire rst,
    input wire cen,          // клок чипа (типично 8 МГц → 15.6 кГц сэмплов при /512)
    input wire [1:0] clkdiv,

    input wire wr,           // строб записи (домен clk, любой длительности)
    input wire addr,         // 0 = управление, 1 = данные
    input wire [7:0] din,

    output wire drq,
    output wire wr_pending,  // предыдущая запись ещё не принята (ждёт cen)
    output wire playing,
    output wire signed [11:0] sound
);

  // ------------------------------------------------------------------
  // Латч записи до ближайшего cen (у e6258 это пара sysclk/sndclk)
  reg pend_wr = 0;
  reg pend_addr = 0;
  reg [7:0] pend_din = 0;

  // ------------------------------------------------------------------
  // Буфер ниблов и управление (процесс 2 из e6258)
  reg playen = 0;
  reg [3:0] nxtbuf0 = 0;
  reg [3:0] nxtbuf1 = 0;
  reg [1:0] bufcount = 0;
  reg drq_r = 0;
  reg play_start = 0;
  reg startup_wait = 0;

  // ------------------------------------------------------------------
  // Тайминг ниблов (процесс 3): /4 и делитель частоты сэмплов
  reg [1:0] sftcount = 0;
  reg [7:0] divcount = 0;
  reg [3:0] playdat = 0;
  reg playwr = 0;
  reg datuse = 0;
  reg datemp = 1;

  wire [7:0] div_reload = clkdiv == 2'b00 ? 8'd255 : clkdiv == 2'b01 ? 8'd191 : 8'd127;

  always @(posedge clk) begin
    if (rst) begin
      pend_wr <= 0;
      playen <= 0;
      nxtbuf0 <= 0;
      nxtbuf1 <= 0;
      bufcount <= 0;
      drq_r <= 0;
      play_start <= 0;
      startup_wait <= 0;
      sftcount <= 0;
      divcount <= 0;
      playdat <= 0;
      playwr <= 0;
      datuse <= 0;
      datemp <= 1;
    end else begin
      if (wr) begin
        pend_wr <= 1;
        pend_addr <= addr;
        pend_din <= din;
      end

      if (cen) begin
        play_start <= 0;
        playwr <= 0;
        datuse <= 0;

        // потребление нибла декодером
        if (datuse) begin
          nxtbuf0 <= nxtbuf1;
          nxtbuf1 <= 0;
          if (bufcount > 0) bufcount <= bufcount - 1'b1;
          if (bufcount <= 1) drq_r <= 1;
        end

        // применение защёлкнутой записи
        if (pend_wr && !wr) begin
          pend_wr <= 0;
          if (!pend_addr) begin
            if (pend_din[0]) begin
              playen <= 0;
              bufcount <= 0;
              nxtbuf0 <= 0;
              nxtbuf1 <= 0;
              drq_r <= 0;
              startup_wait <= 0;
            end else if (pend_din[1]) begin
              if (!playen) begin
                playen <= 1;
                bufcount <= 0;
                nxtbuf0 <= 0;
                nxtbuf1 <= 0;
                drq_r <= 1;
                play_start <= 1;
                startup_wait <= 1;
              end
            end
          end else begin
            drq_r <= 0;
            nxtbuf1 <= pend_din[7:4];
            nxtbuf0 <= pend_din[3:0];
            bufcount <= 2;
            startup_wait <= 0;
          end
        end

        // тайминг выборки ниблов
        if (play_start) begin
          divcount <= 0;
          sftcount <= 0;
        end else if (playen && !startup_wait) begin
          if (sftcount > 0) begin
            sftcount <= sftcount - 1'b1;
          end else begin
            sftcount <= 3;
            if (divcount == 0) begin
              playdat <= nxtbuf0;
              datemp <= bufcount == 0;
              playwr <= 1;
              datuse <= 1;
              divcount <= div_reload;
            end else begin
              divcount <= divcount - 1'b1;
            end
          end
        end
      end
    end
  end

  assign drq = drq_r && !pend_wr;
  assign wr_pending = pend_wr;
  assign playing = playen;

  // ------------------------------------------------------------------
  // Декодер ADPCM (порт calcadpcm.vhd)
  function automatic [10:0] step_value(input [5:0] idx);
    case (idx)
      0: step_value = 16; 1: step_value = 17; 2: step_value = 19; 3: step_value = 21;
      4: step_value = 23; 5: step_value = 25; 6: step_value = 28; 7: step_value = 31;
      8: step_value = 34; 9: step_value = 37; 10: step_value = 41; 11: step_value = 45;
      12: step_value = 50; 13: step_value = 55; 14: step_value = 60; 15: step_value = 66;
      16: step_value = 73; 17: step_value = 80; 18: step_value = 88; 19: step_value = 97;
      20: step_value = 107; 21: step_value = 118; 22: step_value = 130; 23: step_value = 143;
      24: step_value = 157; 25: step_value = 173; 26: step_value = 190; 27: step_value = 209;
      28: step_value = 230; 29: step_value = 253; 30: step_value = 279; 31: step_value = 307;
      32: step_value = 337; 33: step_value = 371; 34: step_value = 408; 35: step_value = 449;
      36: step_value = 494; 37: step_value = 544; 38: step_value = 598; 39: step_value = 658;
      40: step_value = 724; 41: step_value = 796; 42: step_value = 876; 43: step_value = 963;
      44: step_value = 1060; 45: step_value = 1166; 46: step_value = 1282; 47: step_value = 1411;
      default: step_value = 1552;
    endcase
  endfunction

  reg signed [12:0] signal_acc = 0;
  reg [5:0] step_idx = 0;
  reg lplayen = 0;
  reg [8:0] decay_div = 0;

  always @(posedge clk) begin
    if (rst) begin
      signal_acc <= 0;
      step_idx <= 0;
      lplayen <= 0;
      decay_div <= 0;
    end else if (cen) begin
      lplayen <= playen;

      if (playen && !lplayen) begin
        // старт воспроизведения: инициализация как в MAME
        signal_acc <= -13'sd2;
        step_idx <= 0;
        decay_div <= 0;
      end else if (!playen) begin
        // не играем: медленный рамп к нулю против щелчка
        step_idx <= 0;
        if (signal_acc > 0) begin
          if (decay_div == 0) begin
            decay_div <= 9'd399;
            signal_acc <= signal_acc - 1'b1;
          end else decay_div <= decay_div - 1'b1;
        end else if (signal_acc < 0) begin
          if (decay_div == 0) begin
            decay_div <= 9'd399;
            signal_acc <= signal_acc + 1'b1;
          end else decay_div <= decay_div - 1'b1;
        end
      end else if (playwr && datemp) begin
        // буфер пуст: рамп к нулю на частоте сэмплов
        step_idx <= 0;
        if (signal_acc > 0) signal_acc <= signal_acc - 1'b1;
        else if (signal_acc < 0) signal_acc <= signal_acc + 1'b1;
      end else if (playwr) begin
        decay_div <= 0;
        begin : decode
          reg [10:0] stepval;
          reg [12:0] delta;
          reg signed [14:0] nsig;
          reg signed [7:0] nstep;
          stepval = step_value(step_idx);
          delta = {5'b0, stepval[10:3]}
                + (playdat[0] ? {4'b0, stepval[10:2]} : 13'd0)
                + (playdat[1] ? {3'b0, stepval[10:1]} : 13'd0)
                + (playdat[2] ? {2'b0, stepval} : 13'd0);
          nsig = playdat[3] ? signal_acc - $signed({2'b0, delta})
                            : signal_acc + $signed({2'b0, delta});
          if (nsig > 2047) nsig = 2047;
          else if (nsig < -2048) nsig = -2048;
          signal_acc <= nsig[12:0];

          case (playdat[2:0])
            3'd4: nstep = $signed({2'b0, step_idx}) + 8'sd2;
            3'd5: nstep = $signed({2'b0, step_idx}) + 8'sd4;
            3'd6: nstep = $signed({2'b0, step_idx}) + 8'sd6;
            3'd7: nstep = $signed({2'b0, step_idx}) + 8'sd8;
            default: nstep = $signed({2'b0, step_idx}) - 8'sd1;
          endcase
          if (nstep < 0) step_idx <= 0;
          else if (nstep > 48) step_idx <= 48;
          else step_idx <= nstep[5:0];
        end
      end
    end
  end

  assign sound = signal_acc[11:0];

endmodule
