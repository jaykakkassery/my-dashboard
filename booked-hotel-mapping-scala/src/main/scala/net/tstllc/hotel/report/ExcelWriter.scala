package net.tstllc.hotel.report

import org.apache.poi.ss.usermodel._
import org.apache.poi.xssf.usermodel._
import org.apache.poi.ss.util.CellRangeAddress

object ExcelWriter {

  private val FIELDS       = Seq("name", "address", "city", "state", "country", "phone")
  private val FIELD_LABELS = Seq("Property Name", "Address", "City", "State", "Country", "Phone")
  private val NCOLS        = 4 + FIELDS.length * 2

  private def rgb(hex: String): XSSFColor = {
    val b = hex.grouped(2).map(Integer.parseInt(_, 16).toByte).toArray
    new XSSFColor(b, null)
  }

  def write(rows: Seq[ReportRow], outPath: String, displayDate: String): Unit = {
    val wb = new XSSFWorkbook()
    val ws = wb.createSheet("Property Report")

    // ---- colours ----
    val cGreen  = rgb("D4EDDA"); val cYellow = rgb("FFF3CD")
    val cRed    = rgb("F8D7DA"); val cHeader  = rgb("343A40")
    val cTitle  = rgb("1D3557"); val cBorder  = rgb("CCCCCC")

    def makeStyle(fg: XSSFColor, halign: HorizontalAlignment = HorizontalAlignment.LEFT,
                  valign: VerticalAlignment = VerticalAlignment.TOP,
                  wrap: Boolean = true): XSSFCellStyle = {
      val s = wb.createCellStyle().asInstanceOf[XSSFCellStyle]
      s.setFillForegroundColor(fg); s.setFillPattern(FillPatternType.SOLID_FOREGROUND)
      s.setAlignment(halign); s.setVerticalAlignment(valign)
      s.setWrapText(wrap)
      Seq(s.setBorderLeft(_), s.setBorderRight(_), s.setBorderTop(_), s.setBorderBottom(_))
        .foreach(_(BorderStyle.THIN))
      s.setLeftBorderColor(cBorder); s.setRightBorderColor(cBorder)
      s.setTopBorderColor(cBorder);  s.setBottomBorderColor(cBorder)
      s
    }

    val sGreen  = makeStyle(cGreen);  val sYellow = makeStyle(cYellow)
    val sRed    = makeStyle(cRed)
    val sHeader = makeStyle(cHeader, HorizontalAlignment.CENTER, VerticalAlignment.CENTER)
    val sTitle  = makeStyle(cTitle,  HorizontalAlignment.CENTER, VerticalAlignment.CENTER)
    val sNeutral = makeStyle(rgb("FFFFFF"))

    // ---- fonts ----
    def font(color: Short = IndexedColors.AUTOMATIC.getIndex, bold: Boolean = false,
             italic: Boolean = false, size: Short = 11): Font = {
      val f = wb.createFont()
      f.setColor(color); f.setBold(bold); f.setItalic(italic); f.setFontHeightInPoints(size)
      f
    }
    val fWhiteBold = font(IndexedColors.WHITE.getIndex, bold = true)
    val fTitleFont = font(IndexedColors.WHITE.getIndex, bold = true, size = 14)
    val fBold      = font(bold = true)
    val fItalicSm  = font(italic = true, size = 10)

    sHeader.setFont(fWhiteBold); sTitle.setFont(fTitleFont)

    // ---- summary stats ----
    val totalBookings = rows.map(_.booking.bookingIds.size).sum
    val nGreen  = rows.count(_.rowStatus == "green")
    val nYellow = rows.count(_.rowStatus == "yellow")
    val nRed    = rows.count(_.rowStatus == "red")

    // Rows where every field matched (all-green) carry nothing to review — omit them
    // from the report body. Summary counts above still reflect all rows evaluated.
    val displayRows = rows.filter(_.rowStatus != "green")

    var rIdx = 0

    def newRow(height: Float = -1): XSSFRow = {
      val r = ws.createRow(rIdx); rIdx += 1
      if (height > 0) r.setHeightInPoints(height)
      r
    }

    def cell(row: XSSFRow, col: Int, value: String, style: CellStyle): Unit = {
      val c = row.createCell(col); c.setCellValue(value); c.setCellStyle(style)
    }

    def merge(r1: Int, r2: Int, c1: Int, c2: Int): Unit =
      ws.addMergedRegion(new CellRangeAddress(r1, r2, c1, c2))

    // ---- Row 1: title ----
    val titleRow = newRow(28)
    cell(titleRow, 0, s"Hotel Booked Property Information — $displayDate", sTitle)
    merge(0, 0, 0, NCOLS - 1)

    // ---- Row 2: summary counts ----
    val sumRow = newRow(20)
    val sSumLeft = wb.createCellStyle().asInstanceOf[XSSFCellStyle]
    sSumLeft.setFont(fBold)
    cell(sumRow, 0,
      s"Unique Properties: ${rows.size}   |   Total Bookings: $totalBookings   |   " +
        s"Rows shown below: ${displayRows.size} (all-match rows hidden)", sSumLeft)
    merge(1, 1, 0, 3)
    val sGreenC = makeStyle(cGreen, HorizontalAlignment.CENTER, VerticalAlignment.CENTER)
    sGreenC.setFont(fBold)
    cell(sumRow, 4, s"✅ Match: $nGreen", sGreenC);   merge(1, 1, 4, 5)
    val sYellowC = makeStyle(cYellow, HorizontalAlignment.CENTER, VerticalAlignment.CENTER)
    sYellowC.setFont(fBold)
    cell(sumRow, 6, s"⚠️ Review: $nYellow", sYellowC); merge(1, 1, 6, 7)
    val sRedC = makeStyle(cRed, HorizontalAlignment.CENTER, VerticalAlignment.CENTER)
    sRedC.setFont(fBold)
    cell(sumRow, 8, s"❌ Wrong: $nRed", sRedC)

    // ---- Row 3: legend ----
    val legRow = newRow(16)
    val sItalic = wb.createCellStyle().asInstanceOf[XSSFCellStyle]; sItalic.setFont(fItalicSm)
    cell(legRow, 0, "BD = Booking Data (recorded at time of booking)", sItalic); merge(2, 2, 0, 3)
    cell(legRow, 4, "SD = Supplier Data (from supplier reference database)", sItalic); merge(2, 2, 4, NCOLS - 1)

    // ---- Row 4: spacer ----
    newRow()

    // ---- Row 5: headers ----
    val hdrRow = newRow(36)
    val headers = Seq("Booking ID(s)", "Provider", "Provider Code", "TST Hotel ID") ++
      FIELD_LABELS.flatMap(l => Seq(s"BD: $l", s"SD: $l"))
    headers.zipWithIndex.foreach { case (h, i) => cell(hdrRow, i, h, sHeader) }
    ws.createFreezePane(0, rIdx)

    // ---- data rows ----
    val styleFor = Map("green" -> sGreen, "yellow" -> sYellow, "red" -> sRed)

    displayRows.foreach { r =>
      val dataRow = newRow()
      val ids = r.booking.bookingIds.mkString(", ")
      cell(dataRow, 0, ids,                           sNeutral)
      cell(dataRow, 1, r.provider,                    sNeutral)
      cell(dataRow, 2, r.booking.providerCode,        sNeutral)
      cell(dataRow, 3, r.booking.hotelId,             sNeutral)

      r.supply match {
        case None =>
          FIELDS.zipWithIndex.foreach { case (f, i) =>
            cell(dataRow, 4 + i * 2,     r.bd.getOrElse(f, ""), sYellow)
            cell(dataRow, 4 + i * 2 + 1, "— not in Supplier Data —", sYellow)
          }
        case Some(sd) =>
          val sdMap = Map(
            "name" -> sd.name, "address" -> sd.address, "city" -> sd.city,
            "state" -> sd.state, "country" -> sd.country, "phone" -> sd.phone,
          )
          FIELDS.zipWithIndex.foreach { case (f, i) =>
            val s = styleFor.getOrElse(r.statuses.getOrElse(f, "yellow"), sYellow)
            cell(dataRow, 4 + i * 2,     r.bd.getOrElse(f, ""), s)
            cell(dataRow, 4 + i * 2 + 1, sdMap.getOrElse(f, ""), s)
          }
      }
    }

    // ---- column widths ----
    val widths = Seq(28, 14, 16, 14) ++ Seq.fill(FIELDS.length)(Seq(28, 28)).flatten
    widths.zipWithIndex.foreach { case (w, i) =>
      ws.setColumnWidth(i, w * 256)
    }

    val fos = new java.io.FileOutputStream(outPath)
    try wb.write(fos) finally { fos.close(); wb.close() }
  }
}
