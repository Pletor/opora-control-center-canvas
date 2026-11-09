/** A response can finish only the exact mutation that started it. Reads may refresh independently. */
export class ReviewMutations {
  private sequence = 0;
  private active: number | null = null;
  invalidate() {this.sequence++; this.active = null;}
  begin() {if (this.active !== null) return null; return this.active = ++this.sequence;}
  finish(token: number) {if (this.active !== token) return false; this.active = null; return true;}
}
