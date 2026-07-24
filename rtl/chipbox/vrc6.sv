// VRC6 (Konami, Akumajou Densetsu / Madara / Esper Dream 2):
// два прямоугольных канала с 8 скважностями + пилообразный канал.
// Реализация по общедоступному описанию NESdev Wiki.
// Клок — NES CPU (cen ~1.79 МГц), выход 0..61 (p1 15 + p2 15 + saw 31).
module vrc6 (
    input wire clk,
    input wire cen,           // clock-enable частоты CPU
    input wire rst,
    input wire wr,            // строб записи (1 такт clk)
    input wire [1:0] blk,     // 0=$9xxx (pulse1), 1=$Axxx (pulse2), 2=$Bxxx (saw)
    input wire [1:0] rsel,    // младшие биты адреса (регистр 0-3)
    input wire [7:0] din,
    output wire [5:0] out
);

  // $9003: [0] halt, [1] клок пульсов/пилы x16, [2] x256
  reg halt = 0;
  reg x16 = 0;
  reg x256 = 0;

  // Пульс-канал: ctrl {mode[7], duty[6:4], vol[3:0]}, период 12 бит, enable
  reg [7:0] p_ctrl[2];
  reg [11:0] p_per[2];
  reg p_en[2];
  reg [11:0] p_cnt[2];
  reg [3:0] p_step[2];

  // Пила: rate[5:0], период 12 бит, enable
  reg [5:0] s_rate = 0;
  reg [11:0] s_per = 0;
  reg s_en = 0;
  reg [11:0] s_cnt = 0;
  reg [7:0] s_acc = 0;
  reg [3:0] s_step = 0;

  integer i;

  // Эффективный счётный период: x256 сдвигает на 8, x16 на 4
  function automatic [11:0] eff_cnt(input [11:0] per);
    eff_cnt = x256 ? {8'b0, per[11:8]} : x16 ? {4'b0, per[11:4]} : per;
  endfunction

  always @(posedge clk) begin
    if (rst) begin
      halt <= 0;
      x16 <= 0;
      x256 <= 0;
      for (i = 0; i < 2; i = i + 1) begin
        p_ctrl[i] <= 0;
        p_per[i] <= 0;
        p_en[i] <= 0;
        p_cnt[i] <= 0;
        p_step[i] <= 4'hF;
      end
      s_rate <= 0;
      s_per <= 0;
      s_en <= 0;
      s_cnt <= 0;
      s_acc <= 0;
      s_step <= 0;
    end else begin
      if (wr) begin
        case ({blk, rsel})
          4'b00_00: p_ctrl[0] <= din;
          4'b00_01: p_per[0][7:0] <= din;
          4'b00_10: begin
            p_per[0][11:8] <= din[3:0];
            p_en[0] <= din[7];
            if (!din[7]) p_step[0] <= 4'hF; // выключение сбрасывает фазу
          end
          4'b00_11: {x256, x16, halt} <= din[2:0];
          4'b01_00: p_ctrl[1] <= din;
          4'b01_01: p_per[1][7:0] <= din;
          4'b01_10: begin
            p_per[1][11:8] <= din[3:0];
            p_en[1] <= din[7];
            if (!din[7]) p_step[1] <= 4'hF;
          end
          4'b10_00: s_rate <= din[5:0];
          4'b10_01: s_per[7:0] <= din;
          4'b10_10: begin
            s_per[11:8] <= din[3:0];
            s_en <= din[7];
            if (!din[7]) begin
              s_acc <= 0;
              s_step <= 0;
            end
          end
          default: ;
        endcase
      end

      if (cen && !halt) begin
        // пульсы: 16-шаговый секвенсор, выход при step <= duty
        for (i = 0; i < 2; i = i + 1) begin
          if (p_en[i]) begin
            if (p_cnt[i] == 0) begin
              p_cnt[i] <= eff_cnt(p_per[i]);
              p_step[i] <= p_step[i] == 0 ? 4'hF : p_step[i] - 1'b1;
            end else begin
              p_cnt[i] <= p_cnt[i] - 1'b1;
            end
          end
        end
        // пила: 14 тиков на цикл, аккумулятор += rate на чётных шагах
        if (s_en) begin
          if (s_cnt == 0) begin
            s_cnt <= eff_cnt(s_per);
            if (s_step == 4'd13) begin
              s_step <= 0;
              s_acc <= 0;
            end else begin
              s_step <= s_step + 1'b1;
              if (!s_step[0]) s_acc <= s_acc + {2'b0, s_rate};
            end
          end else begin
            s_cnt <= s_cnt - 1'b1;
          end
        end
      end
    end
  end

  wire [3:0] p_out0 = (p_en[0] && (p_ctrl[0][7] || p_step[0] <= {1'b0, p_ctrl[0][6:4]}))
      ? p_ctrl[0][3:0] : 4'd0;
  wire [3:0] p_out1 = (p_en[1] && (p_ctrl[1][7] || p_step[1] <= {1'b0, p_ctrl[1][6:4]}))
      ? p_ctrl[1][3:0] : 4'd0;
  wire [4:0] s_out = s_en ? s_acc[7:3] : 5'd0;

  assign out = {2'b0, p_out0} + {2'b0, p_out1} + {1'b0, s_out};

endmodule
