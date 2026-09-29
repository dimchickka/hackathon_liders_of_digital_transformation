
/* WARNING: Removing unreachable block (ram,0x10000e76) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_10000ab0(void)

{
  byte bVar1;
  char cVar2;
  uint uVar3;
  bool bVar4;
  bool bVar5;
  bool bVar6;
  bool bVar7;
  char *pcVar8;
  byte *pbVar9;
  byte *pbVar10;
  char *pcVar11;
  char *pcVar12;
  int iVar13;
  byte *pbVar14;
  int iVar15;
  uint uVar16;
  byte *pbVar17;
  uint uVar18;
  longlong lVar19;
  longlong lVar20;
  longlong lVar21;
  undefined8 uVar22;
  longlong lVar23;
  int local_54;
  uint local_50;
  int local_4c;
  uint local_48;
  int local_44;
  int local_3c;
  char cStack_2d;
  int local_2c;
  
  FUN_100016b8(0x1d);
  _DAT_d0000028 = 0x20000000;
  FUN_10001568(0x1d,1,0);
  FUN_100016b8(0x1b);
  _DAT_d0000028 = 0x8000000;
  FUN_10001568(0x1b,1,0);
  FUN_100016b8(0x1c);
  _DAT_d0000028 = 0x10000000;
  FUN_10001568(0x1c,1,0);
  pbVar9 = DAT_10000df0;
  pbVar14 = DAT_10000df0 + 10;
  pbVar17 = DAT_10000df0;
  do {
    bVar1 = *pbVar17;
    pbVar17 = pbVar17 + 1;
    FUN_100016b8((uint)bVar1);
    pbVar10 = DAT_10000df4;
    _DAT_d0000018 = 1 << (uint)bVar1;
    _DAT_d0000024 = _DAT_d0000018;
  } while (pbVar14 != pbVar17);
  pbVar14 = DAT_10000df4 + 4;
  pbVar17 = DAT_10000df4;
  do {
    bVar1 = *pbVar17;
    pbVar17 = pbVar17 + 1;
    _DAT_d0000018 = _DAT_d0000024;
    FUN_100016b8((uint)bVar1);
    _DAT_d0000018 = 1 << (uint)bVar1;
    _DAT_d0000024 = _DAT_d0000018;
  } while (pbVar17 != pbVar14);
  FUN_10001204();
  pcVar11 = DAT_10000df8;
  *DAT_10000df8 = '\0';
  pcVar12 = DAT_10000dfc;
  *DAT_10000dfc = '\0';
  pcVar8 = DAT_10000e00;
  pcVar8[0] = '\0';
  pcVar8[1] = '\0';
  pcVar8[2] = '\0';
  pcVar8[3] = '\0';
  FUN_100015e8(0x1d,0xc,1,DAT_10000e04);
  FUN_10001590(0x1b,0xc,1);
  FUN_10001590(0x1c,4,1);
  local_2c = 0;
  _DAT_d0000018 = 0x100;
  _DAT_d0000014 = 0x80;
  FUN_10001218(0,0,0x20);
  lVar19 = FUN_100025c8();
  iVar13 = DAT_10000e10;
  lVar19 = lVar19 + (ulonglong)DAT_10000e08;
  if (lVar19 < 0) {
    lVar19 = CONCAT44(DAT_10000e0c,0xffffffff);
  }
  local_3c = 0;
  lVar23 = 0;
  lVar21 = 0;
  bVar5 = false;
  local_54 = 0;
  bVar6 = false;
  cVar2 = *pcVar11;
  uVar18 = 0;
  iVar15 = local_54;
  bVar7 = false;
  do {
    local_50 = (uint)lVar21;
    local_4c = (int)((ulonglong)lVar21 >> 0x20);
    if (cVar2 == '\0') {
      if (bVar5) {
        uVar22 = FUN_100025c8();
        uVar16 = local_4c - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_50 < (uint)uVar22);
        bVar5 = true;
        if (((int)(uVar16 - uVar3) < 1) && ((uVar16 != uVar3 || (local_50 == (uint)uVar22)))) {
          if (iVar15 < 1) {
            if (iVar15 != 0) {
              local_3c = -1;
              bVar5 = false;
              goto LAB_10000dbe;
            }
          }
          else {
            local_3c = 1;
          }
          goto LAB_10000dba;
        }
      }
      else {
LAB_10000dba:
        bVar5 = false;
      }
LAB_10000dbe:
      bVar4 = false;
      local_54 = iVar15;
      if (bVar7) {
LAB_10000c3e:
        local_44 = (int)((ulonglong)lVar23 >> 0x20);
        local_48 = (uint)lVar23;
        uVar22 = FUN_100025c8();
        uVar16 = local_44 - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_48 < (uint)uVar22);
        if (((int)(uVar16 - uVar3) < 1) && ((uVar16 != uVar3 || (local_48 == (uint)uVar22)))) {
          bVar4 = false;
          if (local_3c != 0) {
            uVar16 = (uint)*(byte *)((int)&local_2c + uVar18);
            if (local_3c == -1) goto LAB_100010ac;
            goto LAB_10001052;
          }
        }
        else {
          bVar4 = true;
        }
      }
    }
    else {
      local_54 = (int)cVar2;
      *pcVar11 = '\0';
      if (!bVar7) {
        lVar23 = FUN_100025c8();
        lVar23 = lVar23 + (ulonglong)DAT_100010fc;
        if (lVar23 < 0) {
          lVar23 = CONCAT44(DAT_100010f4,0xffffffff);
        }
        local_3c = 0;
      }
      local_44 = (int)((ulonglong)lVar23 >> 0x20);
      local_48 = (uint)lVar23;
      if (bVar5) {
        local_54 = iVar15 + local_54;
        uVar22 = FUN_100025c8();
        uVar16 = local_4c - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_50 < (uint)uVar22);
        if ((0 < (int)(uVar16 - uVar3)) || ((uVar16 == uVar3 && (local_50 != (uint)uVar22))))
        goto LAB_10000c3e;
        bVar4 = true;
        if (local_54 < 1) {
          bVar5 = false;
          if (local_54 == 0) goto LAB_10000c3e;
          uVar22 = FUN_100025c8();
          uVar16 = local_44 - (int)((ulonglong)uVar22 >> 0x20);
          uVar3 = (uint)(local_48 < (uint)uVar22);
          if (((int)(uVar16 - uVar3) < 1) && ((uVar16 != uVar3 || (local_48 == (uint)uVar22)))) {
            uVar16 = (uint)*(byte *)((int)&local_2c + uVar18);
            bVar5 = false;
            goto LAB_100010ac;
          }
          local_3c = -1;
          bVar5 = false;
          goto LAB_10000c62;
        }
        uVar22 = FUN_100025c8();
        uVar16 = local_44 - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_48 < (uint)uVar22);
        if ((0 < (int)(uVar16 - uVar3)) || ((uVar16 == uVar3 && (local_48 != (uint)uVar22)))) {
          local_3c = 1;
          bVar5 = false;
          goto LAB_10000c62;
        }
        uVar16 = (uint)*(byte *)((int)&local_2c + uVar18);
        bVar5 = false;
LAB_10001052:
        iVar15 = uVar16 - 1;
        if (uVar16 != 0) {
          local_3c = 1;
          goto joined_r0x100010b6;
        }
        local_3c = 1;
        iVar15 = 9;
      }
      else {
        lVar21 = FUN_100025c8();
        lVar21 = lVar21 + (ulonglong)DAT_100010f8;
        if (lVar21 < 0) {
          lVar21 = CONCAT44(DAT_100010f4,0xffffffff);
        }
        local_4c = (int)((ulonglong)lVar21 >> 0x20);
        local_50 = (uint)lVar21;
        uVar22 = FUN_100025c8();
        uVar16 = local_4c - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_50 < (uint)uVar22);
        if ((0 < (int)(uVar16 - uVar3)) || ((uVar16 == uVar3 && (local_50 != (uint)uVar22)))) {
          bVar5 = true;
          goto LAB_10000c3e;
        }
        if (0 < local_54) {
          uVar22 = FUN_100025c8();
          uVar16 = local_44 - (int)((ulonglong)uVar22 >> 0x20);
          uVar3 = (uint)(local_48 < (uint)uVar22);
          if (((int)(uVar16 - uVar3) < 1) && ((uVar16 != uVar3 || (local_48 == (uint)uVar22)))) {
            uVar16 = (uint)*(byte *)((int)&local_2c + uVar18);
            goto LAB_10001052;
          }
          local_3c = 1;
          bVar4 = true;
          goto LAB_10000c62;
        }
        uVar22 = FUN_100025c8();
        uVar16 = local_44 - (int)((ulonglong)uVar22 >> 0x20);
        uVar3 = (uint)(local_48 < (uint)uVar22);
        if ((0 < (int)(uVar16 - uVar3)) || ((uVar16 == uVar3 && (local_48 != (uint)uVar22)))) {
          local_3c = -1;
          bVar4 = true;
          goto LAB_10000c62;
        }
        uVar16 = (uint)*(byte *)((int)&local_2c + uVar18);
LAB_100010ac:
        iVar15 = uVar16 + 1;
        local_3c = -1;
joined_r0x100010b6:
        for (; 9 < iVar15; iVar15 = iVar15 + -10) {
        }
      }
      *(char *)((int)&local_2c + uVar18) = (char)iVar15;
      _DAT_d0000018 = 0x100;
      _DAT_d0000014 = 1 << pbVar9[iVar15];
      bVar4 = false;
    }
LAB_10000c62:
    if (*pcVar12 == '\0') {
LAB_10000d92:
      lVar20 = FUN_100025c8();
      lVar20 = lVar19 - lVar20;
    }
    else {
      *pcVar12 = '\0';
      if (2 < uVar18) {
        iVar15 = 1;
        pcVar8[uVar18] = '\x01';
        while ((&cStack_2d)[iVar15] == *(char *)(iVar13 + iVar15)) {
          iVar15 = iVar15 + 1;
          FUN_1000239c(0x32);
          if (iVar15 == 5) {
            FUN_10001218(0,0x20,0);
            _DAT_d0000014 = 0x400;
            *DAT_10000e14 = 1;
            return;
          }
        }
        iVar15 = 3;
        _DAT_d0000014 = 0x400;
        do {
          FUN_10001218(0x20,0,0);
          FUN_1000239c(200);
          FUN_10001218(0,0,0);
          iVar15 = iVar15 + -1;
          FUN_1000239c(200);
        } while (iVar15 != 0);
        pcVar8[0] = '\0';
        pcVar8[1] = '\0';
        pcVar8[2] = '\0';
        pcVar8[3] = '\0';
        _DAT_d0000018 = 0x100;
        _DAT_d0000014 = 0x80;
        local_2c = iVar15;
        FUN_10001218(0,0,0x20);
        lVar19 = FUN_100025c8();
        lVar19 = lVar19 + (ulonglong)DAT_10000e08;
        if (lVar19 < 0) {
          lVar19 = CONCAT44(DAT_10000e0c,0xffffffff);
        }
        uVar18 = 0;
        bVar6 = false;
        goto LAB_10000d92;
      }
      pcVar8[uVar18] = '\x01';
      uVar18 = uVar18 + 1 & 0xff;
      _DAT_d0000018 = 0x100;
      if (9 < *(byte *)((int)&local_2c + uVar18)) goto LAB_10000d92;
      _DAT_d0000014 = 1 << (uint)pbVar9[*(byte *)((int)&local_2c + uVar18)];
      lVar20 = FUN_100025c8();
      lVar20 = lVar19 - lVar20;
    }
    iVar15 = _DAT_d0000014;
    if (lVar20 < 1) {
      lVar19 = FUN_100025c8();
      lVar19 = lVar19 + (ulonglong)DAT_100010f0;
      if (lVar19 < 0) {
        lVar19 = CONCAT44(DAT_100010f4,0xffffffff);
      }
      bVar6 = (bool)(bVar6 ^ 1);
      _DAT_d0000018 = 0x400;
      if (*pcVar8 != '\0') {
        _DAT_d0000014 = 0x2000;
      }
      if (pcVar8[1] != '\0') {
        _DAT_d0000014 = 0x1000;
      }
      if (pcVar8[2] != '\0') {
        _DAT_d0000014 = 0x800;
      }
      if (pcVar8[3] != '\0') {
        _DAT_d0000014 = 0x400;
      }
      iVar15 = _DAT_d0000014;
      if ((pcVar8[uVar18] == '\0') && (iVar15 = 1 << pbVar10[uVar18], !bVar6)) {
        iVar15 = _DAT_d0000014;
        _DAT_d0000018 = 1 << pbVar10[uVar18];
      }
    }
    _DAT_d0000014 = iVar15;
    FUN_1000239c(2);
    cVar2 = *pcVar11;
    iVar15 = local_54;
    bVar7 = bVar4;
  } while( true );
}

