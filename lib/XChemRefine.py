# last edited: 08/08/2017, 15:00

import pygtk

pygtk.require('2.0')
import gtk, pango

import os
import glob
import sys
import getpass
import fileinput
import time
#sys.path.append(os.path.join(os.getenv('CCP4'),'lib/python2.7/site-packages'))
#import coot
#sys.path.append('/usr/local/coot/SoakProc/lib')
#import coot_utils_XChem

sys.path.append(os.getenv('XChemExplorer_DIR')+'/lib')
import XChemLog
from XChemUtils import pdbtools


def GetSerial(ProjectPath,xtalID):
    # check if there were already previous refinements
    # if no: create a folder Refine_1
    # if yes: create a folder Refine_<max+1>
    temp = []
    found = 0
    if os.path.isdir(os.path.join(ProjectPath,xtalID)):
        for item in glob.glob(os.path.join(ProjectPath,xtalID,'*')):
            if item.startswith(os.path.join(ProjectPath,xtalID,'Refine_')):
                    print int(item[item.rfind('_')+1:])
                    temp.append(int(item[item.rfind('_')+1:]))
                    found = 1
    if found:
        Serial = max(temp) + 1
    else:
        Serial=1
    return Serial



class RefineParams(object):

    def __init__(self,ProjectPath,xtalID,compoundID,datasource):
        self.ProjectPath = ProjectPath
        self.xtalID = xtalID
        self.compoundID = compoundID
        self.prefix = 'refine'
        self.datasource=datasource


    def RefmacRefinementParams(self,RefmacParams):
        self.RefmacParams=RefmacParams
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", gtk.main_quit)
        self.window.set_border_width(10)
        self.window.set_title("Refmac Parameters")
        self.vbox = gtk.VBox()

        self.hbox1=gtk.HBox()
        self.hbox1.add(gtk.Label('Refine'))
        self.cb = gtk.combo_box_new_text()
        self.cb.connect("changed", self.ChooseBfacRefinement)
        for item in ['isotropic','anisotropic']:
            self.cb.append_text(item)
        if 'ISOT' in self.RefmacParams['BREF']:
            self.cb.set_active(0)
        if 'ANIS' in self.RefmacParams['BREF']:
            self.cb.set_active(1)
        self.hbox1.add(self.cb)
        self.hbox1.add(gtk.Label('temperature factors'))
        self.vbox.add(self.hbox1)

        self.hbox2=gtk.HBox()
        self.hbox2.add(gtk.Label('Number of Cycles: '))
        self.Ncycles=gtk.Entry()
        self.Ncycles.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.Ncycles.connect("key-release-event", self.on_key_release_Ncycles)
        self.Ncycles.set_text(self.RefmacParams['NCYCLES'])
        self.hbox2.add(self.Ncycles)
        self.vbox.add(self.hbox2)

        self.hbox3=gtk.HBox()
        self.hbox3.add(gtk.Label('MATRIX WEIGHT: '))
        self.MATRIX_WEIGHT=gtk.Entry()
        self.MATRIX_WEIGHT.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.MATRIX_WEIGHT.connect("key-release-event", self.on_key_release_MATRIX_WEIGHT)
        self.MATRIX_WEIGHT.set_text(self.RefmacParams['MATRIX_WEIGHT'])
        self.hbox3.add(self.MATRIX_WEIGHT)
        self.vbox.add(self.hbox3)

        self.TLS = gtk.CheckButton('TLS (find TLS groups with phenix.find_tls_groups)')
        self.TLS.connect("toggled", self.TLSCallback)
        if self.RefmacParams['TLS']=='refi tlsc 10\n': self.TLS.set_active(True)
        self.vbox.pack_start(self.TLS,False)

        self.NCS = gtk.CheckButton('NCS (if applicable')
        self.NCS.connect("toggled", self.NCSCallback)
        if self.RefmacParams['NCS']=='NCSR LOCAL\n': self.NCS.set_active(True)
        self.vbox.pack_start(self.NCS,False)

        self.TWIN = gtk.CheckButton('Twin?')
        self.TWIN.connect("toggled", self.TWINCallback)
        if self.RefmacParams['TWIN']=='TWIN\n': self.TWIN.set_active(True)
        self.vbox.pack_start(self.TWIN,False)

        self.OKbutton = gtk.Button(label="OK")
        self.OKbutton.connect("clicked",self.OK)
        self.vbox.add(self.OKbutton)

        self.window.add(self.vbox)
        self.window.show_all()
        return self.RefmacParams


    def TLSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TLS']='refi tlsc 10\n'
            self.RefmacParams['TLSIN']='refmac.tls\n'
            self.RefmacParams['TLSOUT']='out.tls\n'
            self.RefmacParams['TLSADD']='TLSO ADDU\n'
        else:
            self.RefmacParams['TLS']=''
            self.RefmacParams['TLSIN']=''
            self.RefmacParams['TLSOUT']=''
            self.RefmacParams['TLSADD']=''
        return self.RefmacParams

    def NCSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['NCS']='NCSR LOCAL\n'
        else:
            self.RefmacParams['NCS']=''
        return self.RefmacParams

    def ChooseBfacRefinement(self,widget):
        if widget.get_active_text()=='isotropic':
            self.RefmacParams['BREF']='    bref ISOT\n'
        if widget.get_active_text()=='anisotropic':
            self.RefmacParams['BREF']='    bref ANIS\n'
        return self.RefmacParams

    def on_key_release_Ncycles(self, widget, event):
        print widget.get_text()
        self.RefmacParams['NCYCLES'] = widget.get_text()
        return self.RefmacParams

    def on_key_release_MATRIX_WEIGHT(self, widget, event):
        self.RefmacParams['MATRIX_WEIGHT'] = widget.get_text()
        return self.RefmacParams

    def TWINCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TWIN']='TWIN\n'
        else:
            self.RefmacParams['TWIN']=''
        return self.RefmacParams

    def OK(self,widget):
        self.window.destroy()


    def ParamsFromPreviousCycle(self,Serial):

        RefmacParams={ 'HKLIN': '', 'HKLOUT': '',
                       'XYZIN': '', 'XYZOUT': '',
                       'LIBIN': '', 'LIBOUT': '',
                       'TLSIN': '', 'TLSOUT': '',
                       'TLSADD': '',
                       'NCYCLES': '10',
                       'MATRIX_WEIGHT': 'AUTO',
                       'BREF':   '    bref ISOT\n',
                       'TLS':    '',
                       'NCS':    '',
                       'TWIN':   ''    }

        if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
            for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
                if line.startswith('refi tlsc'):
                    RefmacParams['TLS']=line
                if line.startswith('TLSO'):
                    RefmacParams['TLSADD']=line
                if line.startswith('NCSR LOCAL'):
                    RefmacParams['NCS']=line
                if line.startswith('    bref '):
                    RefmacParams['BREF']=line
                if line.startswith('ncyc'):
                    RefmacParams['Ncycles'] = line.split()[1]
                if line.startswith('weight'):
                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
                if line.startswith('TWIN'):
                    RefmacParams['TWIN']=line
        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refmac.csh')):
            for line in open(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refmac.csh')):
                if line.startswith('refi tlsc'):
                    RefmacParams['TLS']=line
                if line.startswith('TLSO'):
                    RefmacParams['TLSADD']=line
                if line.startswith('NCSR LOCAL'):
                    RefmacParams['NCS']=line
                if line.startswith('    bref '):
                    RefmacParams['BREF']=line
                if line.startswith('ncyc'):
                    RefmacParams['Ncycles'] = line.split()[1]
                if line.startswith('weight'):
                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
                if line.startswith('TWIN'):
                    RefmacParams['TWIN']=line

        return RefmacParams

    def GetRefinementHistory(self):
#        RefinementHistory=''
        RefinementCycle = []
        RcrystList=[]
        RfreeList=[]

        found = False
        for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
            if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
                    print item[item.rfind('_')+1:]
                    RefinementCycle.append(int(item[item.rfind('_')+1:]))
                    found = True
        if found:
            for cycle in sorted(RefinementCycle):
#            for cycle in RefinementCycle:
#                Rcryst=0
#                Rfree=0
#                LigandCC=0
                try:
                    found_Rcryst=False
                    found_Rfree=False
                    newestPDB = max(glob.iglob(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/refine_'+str(cycle)+'.pdb'), key=os.path.getctime)
                    for line in open(newestPDB):
                        if line.startswith('REMARK   3   R VALUE     (WORKING + TEST SET) :'):
                            Rcryst = line.split()[9]
                            RcrystList.append(float(Rcryst))
                            found_Rcryst=True
                        if line.startswith('REMARK   3   FREE R VALUE                     :'):
                            Rfree = line.split()[6]
                            RfreeList.append(float(Rfree))
                            found_Rfree=True
                    if not found_Rcryst:
                        RcrystList.append(0)
                    if not found_Rfree:
                        RfreeList.append(0)
#                    if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                        for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                                if line.startswith('|  LIG'): LigandCC = line.split()[6]
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
                except ValueError:
                    RcrystList.append(0)
                    RfreeList.append(0)
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
        else:
            RefinementCycle = [0]
            RcrystList=[0]
            RfreeList=[0]
        print RefinementCycle,RcrystList,RfreeList
        return(sorted(RefinementCycle),RcrystList,RfreeList)





class Refine(object):

    def __init__(self,ProjectPath,xtalID,compoundID,datasource):
        self.ProjectPath = ProjectPath
        self.xtalID = xtalID
        self.compoundID = compoundID
        self.prefix = 'refine'
        self.datasource=datasource

    def GetSerial(self):
        # check if there were already previous refinements
        # if no: create a folder Refine_1
        # if yes: create a folder Refine_<max+1>
        temp = []
        found = 0
        if os.path.isdir(os.path.join(self.ProjectPath,self.xtalID)):
            for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
                if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
                        print int(item[item.rfind('_')+1:])
                        temp.append(int(item[item.rfind('_')+1:]))
                        found = 1
        if found:
            Serial = max(temp) + 1
        else:
            Serial=1
        return Serial


    def make_covalent_link(self,covLinkAtomSpec,Logfile):
        residuesToModify = ['CYS','SER']

        atom1 = covLinkAtomSpec[1][5]
        atom2 = covLinkAtomSpec[2][5]
        residue_1 = covLinkAtomSpec[3]
        residue_2 = covLinkAtomSpec[4]

        if residue_2 in residuesToModify:
            bond_text = 'LINK: RES-NAME-1 %s FILE-1 %s_acedrg.cif ATOM-NAME-1  %s  RES-NAME-2 %s ATOM-NAME-2  %s' %(residue_1,self.compoundID,atom1,residue_2,atom2)
        else:
            bond_text = 'LINK: RES-NAME-1 %s FILE-1 %s_acedrg.cif ATOM-NAME-1  %s  RES-NAME-2 %s ATOM-NAME-2  %s' % (residue_2, self.compoundID, atom2, residue_1, atom1)

        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
        f = open('covalent_bond.txt','w')
        f.write(bond_text)
        f.close()

        # seems somewhat unncessary, but acedrg does not like some certain descriptions generated by phenix.elbow
        os.system('acedrg -c %s.cif -o %s_acedrg' %(self.compoundID,self.compoundID))

        os.system('acedrg -L covalent_bond.txt -o %s' %self.compoundID)

        if os.path.isfile('%s_link.cif' %self.compoundID):
            Logfile.insert('succefully created link file %s_link.cif' %self.compoundID)
            os.system('/bin/rm %s.cif' %self.compoundID)
            os.system('ln -s %s_link.cif %s.cif' %(self.compoundID,self.compoundID))
        else:
            Logfile.error('could not create linkfile; please check logs in %s/%s' %(self.ProjectPath,self.xtalID))


    def RunRefmac(self,Serial,RefmacParams,external_software,xce_logfile,covLinkAtomSpec):

        if os.path.isfile(xce_logfile): Logfile=XChemLog.updateLog(xce_logfile)
        Serial=str(Serial)

        if covLinkAtomSpec is not None:
            self.make_covalent_link(covLinkAtomSpec,Logfile)

        # first check if refinement is ongoing and exit if yes
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'REFINEMENT_IN_PROGRESS')):
#            coot.info_dialog('*** REFINEMENT IN PROGRESS ***')
            Logfile.insert('cannot start new refinement for %s: *** REFINEMENT IN PROGRESS ***' %self.xtalID)
            return None

        #######################################################
        # HKLIN & HKLOUT
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz')):
            RefmacParams['HKLIN']='HKLIN '+os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz \\\n')
#        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
#            RefmacParams['HKLIN']='HKLIN '+os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz \\\n')
        else:
            Logfile.insert('%s: cannot find HKLIN for refinement; aborting...' %self.xtalID)
            return None
        RefmacParams['HKLOUT']='HKLOUT '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.mtz \\\n')

        #######################################################
        # XYZIN & XYZOUT
        RefmacParams['XYZIN']='XYZIN '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'in.pdb \\\n')
        RefmacParams['XYZOUT']='XYZOUT '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.pdb \\\n')

        #######################################################
        # LIBIN & LIBOUT
        found_cif=False
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.compoundID+'.cif')):
            RefmacParams['LIBIN']='LIBIN '+self.ProjectPath+'/'+self.xtalID+'/'+self.compoundID+'.cif \\\n'
            RefmacParams['LIBOUT']='LIBOUT '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refine_'+Serial+'.cif \\\n'

        #######################################################
        # TLSIN & TLSOUT
        findTLS='\n'
        TLSphenix=''
        if RefmacParams['TLS'].startswith('refi'):
            if external_software['phenix.find_tls_groups']:
                findTLS=os.path.join(os.getenv('XChemExplorer_DIR'),'helpers','phenix_find_TLS_groups.py')+' in.pdb\n'
                RefmacParams['TLSIN']='TLSIN '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refmac.tls \\\n'
                RefmacParams['TLSOUT']='TLSOUT '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refine.tls \\\n'
                TLSphenix=' phenix.tls '
            else:
                RefmacParams['TLS']='\n'

        print '==> XCE: assembling refmac.csh'

        #######################################################
        # we write 'REFINEMENT_IN_PROGRESS' immediately to avoid unncessary refiment
        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
        os.system('touch REFINEMENT_IN_PROGRESS')

        #######################################################
        # Database updates:
        # no DB will be specified when a reference model is built and refined
        refinementStatus=''
        updateDB=''
        if os.path.isfile(self.datasource):
            refinementStatus='$CCP4/bin/ccp4-python $XChemExplorer_DIR/helpers/update_status_flag.py %s %s %s %s\n' %(self.datasource,self.xtalID,'RefinementStatus','running')
            updateDB = (    '$CCP4/bin/ccp4-python '+os.path.join(os.getenv('XChemExplorer_DIR'),'helpers','update_data_source_after_refinement.py')+
                            ' %s %s %s %s\n' %(self.datasource,self.xtalID,self.ProjectPath,os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))    )


        #######################################################
        # clean up!
        # and remove all files which will be re-created by current refinement cycle
        os.system('/bin/rm refine.pdb refine.mtz refine.split.bound-state.pdb validation_summary.txt validate_ligands.txt 2fofc.map fofc.map refine_molprobity.log')

        if external_software['qsub']:
            pbs_line='#PBS -joe -N XCE_refmac\n'
        else:
            pbs_line='\n'

        #######################################################
        # weight
        if str(RefmacParams['MATRIX_WEIGHT']).lower() == 'auto':
            weight='weight AUTO\n'
        else:
            weight='weight matrix '+str(RefmacParams['MATRIX_WEIGHT'])+'\n'

        #######################################################
        # PHENIX stuff (if working at DLS)
        module_load=''
        if os.getcwd().startswith('/dls'):
            module_load='module load phenix\n'

        source =''
        if 'bash' in os.getenv('SHELL'):
            source = (
                'export XChemExplorer_DIR="'+os.getenv('XChemExplorer_DIR')+'"\n'
                '\n'
                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','xce.setup-sh')+'\n'
                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh')+'\n'   )
        elif 'csh' in os.getenv('SHELL'):
            source = (
                'setenv XChemExplorer_DIR '+os.getenv('XChemExplorer_DIR')+'\n'
                '\n'
                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','xce.setup-csh')+'\n'
                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-csh')+'\n'   )


        spider_plot=''
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')):
            if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
                pdb_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')
                mtz_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')
                pdb_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+str(Serial),'refine_'+str(Serial)+'.pdb')
                mtz_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+str(Serial),'refine_'+str(Serial)+'.mtz')
                spider_plot = (
                'cd ' + self.ProjectPath + '/' + self.xtalID + '/Refine_' + Serial + '\n'
                '\n'
#                'giant.merge_conformations '
#                ' major=../refine.split.ground-state.pdb'
#                ' minor=../refine.split.bound-state.pdb'
#                ' reset_all_occupancies=False options.major_occupancy=1.0 options.minor_occupancy=1.0\n'
                'giant.score_model pdb1=%s mtz1=%s pdb2=%s mtz2=%s res_names=LIG,UNL,DRG,FRG\n' % (pdb_one, mtz_one, pdb_two, mtz_two)
                )


        refmacCmds = (
            '#!'+os.getenv('SHELL')+'\n'
            +pbs_line+
            '\n'
            + module_load +
            '\n'
            +source+
            'cd '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'\n'
            '\n'
            +refinementStatus+
            '\n'
            +findTLS+
            'refmac5 '
            +RefmacParams['HKLIN']
            +RefmacParams['HKLOUT']
            +RefmacParams['XYZIN']
            +RefmacParams['XYZOUT']
            +RefmacParams['LIBIN']
            +RefmacParams['LIBOUT']
            +RefmacParams['TLSIN']
            +RefmacParams['TLSOUT']+
            ' << EOF > refmac.log\n'
            'make -\n'
            '    hydrogen ALL -\n'
            '    hout NO -\n'
            '    peptide NO -\n'
            '    cispeptide YES -\n'
            '    ssbridge YES -\n'
            '    symmetry YES -\n'
            '    sugar YES -\n'
            '    connectivity NO -\n'
            '    link NO\n'
            +RefmacParams['NCS']+
            'refi -\n'
            '    type REST -\n'
            '    resi MLKF -\n'
            '    meth CGMAT -\n'
            +RefmacParams['BREF']
            +RefmacParams['TLS']
            +RefmacParams['TWIN']+
            'ncyc '+RefmacParams['NCYCLES']+'\n'
            'scal -\n'
            '    type SIMP -\n'
            '    LSSC -\n'
            '    ANISO -\n'
            '    EXPE\n'
            +weight+
            'solvent YES\n'
            'monitor MEDIUM -\n'
            '    torsion 10.0 -\n'
            '    distance 10.0 -\n'
            '    angle 10.0 -\n'
            '    plane 10.0 -\n'
            '    chiral 10.0 -\n'
            '    bfactor 10.0 -\n'
            '    bsphere 10.0 -\n'
            '    rbond 10.0 -\n'
            '    ncsr 10.0\n'
            'labin  FP=F SIGFP=SIGF FREE=FreeR_flag\n'
            'labout  FC=FC FWT=FWT PHIC=PHIC PHWT=PHWT DELFWT=DELFWT PHDELWT=PHDELWT FOM=FOM\n'
            +RefmacParams['TLSADD']+'\n'
            'DNAME '+self.xtalID+'\n'
            'END\n'
            'EOF\n'
            '\n'
            'phenix.molprobity refine_%s.pdb refine_%s.mtz\n' %(Serial,Serial)+
            '/bin/mv molprobity.out refine_molprobity.log\n'
            'mmtbx.validate_ligands refine_%s.pdb refine_%s.mtz LIG > validate_ligands.txt\n' %(Serial,Serial)+
            'cd '+self.ProjectPath+'/'+self.xtalID+'\n'
            '#ln -s %s/%s/Refine_%s/refine_%s.pdb refine.pdb\n' %(self.ProjectPath,self.xtalID,Serial,Serial)+
            '#ln -s %s/%s/Refine_%s/refine_%s.mtz refine.mtz\n' %(self.ProjectPath,self.xtalID,Serial,Serial)+
            'ln -s ./Refine_%s/refine_%s.pdb refine.pdb\n' %(Serial,Serial)+
            'ln -s ./Refine_%s/refine_%s.mtz refine.mtz\n' %(Serial,Serial)+
            'ln -s refine.pdb refine.split.bound-state.pdb\n'
            '\n'
            'ln -s Refine_%s/validate_ligands.txt .\n' %Serial+
            'ln -s Refine_%s/refine_molprobity.log .\n' %Serial+
            'mmtbx.validation_summary refine.pdb > validation_summary.txt\n'
            '\n'
            'fft hklin refine.mtz mapout 2fofc.map << EOF\n'
            'labin F1=FWT PHI=PHWT\n'
            'EOF\n'
            '\n'
            'fft hklin refine.mtz mapout fofc.map << EOF\n'
            'labin F1=DELFWT PHI=PHDELWT\n'
            'EOF\n'
             '\n'
            +updateDB+
            '\n'
            '/bin/rm %s/%s/REFINEMENT_IN_PROGRESS\n' %(self.ProjectPath,self.xtalID)+
            '\n'
            'cd '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'\n'
            '\n'
            +spider_plot+
            '\n'
           )

        if os.path.isfile(xce_logfile): Logfile.insert('writing refinement shell script to'+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refmac.csh'))
        cmd = open(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refmac.csh'),'w')
        cmd.write(refmacCmds)
        cmd.close()

        os.chdir(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
#        os.system('ssh artemis "cd %s/%s/Refine_%s; qsub refmac.csh"' %(self.ProjectPath,self.xtalID,Serial))
        if os.path.isfile(xce_logfile): Logfile.insert('changing directory to %s' %(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial)))
        if external_software['qsub_remote'] != '':
            print os.getenv('LD_LIBRARY_PATH')
            if os.path.isfile(xce_logfile): Logfile.insert('starting refinement on remote cluster')
            remote_command=external_software['qsub_remote'].replace("qsub'",'cd %s; qsub' %os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
            os.system("%s -P labxchem -q medium.q refmac.csh'" %remote_command)
            print '%s -P labxchem -q medium.q refmac.csh' %remote_command

        elif external_software['qsub'] and not os.uname()[1] == 'hestia':
            Logfile.insert('starting refinement on cluster')
            os.system("qsub -P labxchem -q medium.q refmac.csh")

        else:
            os.system('chmod +x refmac.csh')
            if os.path.isfile(xce_logfile): Logfile.insert('starting refinement on local machine')
            os.system('./refmac.csh &')



    def RefinementParams(self,RefmacParams):
        self.RefmacParams=RefmacParams
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", gtk.main_quit)
        self.window.set_border_width(10)
        self.window.set_title("Refmac Parameters")
        self.vbox = gtk.VBox()

        self.hbox1=gtk.HBox()
        self.hbox1.add(gtk.Label('Refine'))
        self.cb = gtk.combo_box_new_text()
        self.cb.connect("changed", self.ChooseBfacRefinement)
        for item in ['isotropic','anisotropic']:
            self.cb.append_text(item)
        if 'ISOT' in self.RefmacParams['BREF']:
            self.cb.set_active(0)
        if 'ANIS' in self.RefmacParams['BREF']:
            self.cb.set_active(1)
        self.hbox1.add(self.cb)
        self.hbox1.add(gtk.Label('temperature factors'))
        self.vbox.add(self.hbox1)

        self.hbox2=gtk.HBox()
        self.hbox2.add(gtk.Label('Number of Cycles: '))
        self.Ncycles=gtk.Entry()
        self.Ncycles.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.Ncycles.connect("key-release-event", self.on_key_release_Ncycles)
        self.Ncycles.set_text(self.RefmacParams['NCYCLES'])
        self.hbox2.add(self.Ncycles)
        self.vbox.add(self.hbox2)

        self.hbox3=gtk.HBox()
        self.hbox3.add(gtk.Label('MATRIX WEIGHT: '))
        self.MATRIX_WEIGHT=gtk.Entry()
        self.MATRIX_WEIGHT.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.MATRIX_WEIGHT.connect("key-release-event", self.on_key_release_MATRIX_WEIGHT)
        self.MATRIX_WEIGHT.set_text(self.RefmacParams['MATRIX_WEIGHT'])
        self.hbox3.add(self.MATRIX_WEIGHT)
        self.vbox.add(self.hbox3)

        self.TLS = gtk.CheckButton('TLS (find TLS groups with phenix.find_tls_groups)')
        self.TLS.connect("toggled", self.TLSCallback)
        if self.RefmacParams['TLS']=='refi tlsc 10\n': self.TLS.set_active(True)
        self.vbox.pack_start(self.TLS,False)

        self.NCS = gtk.CheckButton('NCS (if applicable')
        self.NCS.connect("toggled", self.NCSCallback)
        if self.RefmacParams['NCS']=='NCSR LOCAL\n': self.NCS.set_active(True)
        self.vbox.pack_start(self.NCS,False)

        self.TWIN = gtk.CheckButton('Twin?')
        self.TWIN.connect("toggled", self.TWINCallback)
        if self.RefmacParams['TWIN']=='TWIN\n': self.TWIN.set_active(True)
        self.vbox.pack_start(self.TWIN,False)

        self.OKbutton = gtk.Button(label="OK")
        self.OKbutton.connect("clicked",self.OK)
        self.vbox.add(self.OKbutton)

        self.window.add(self.vbox)
        self.window.show_all()
        return self.RefmacParams


    def TLSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TLS']='refi tlsc 10\n'
            self.RefmacParams['TLSIN']='refmac.tls\n'
            self.RefmacParams['TLSOUT']='out.tls\n'
            self.RefmacParams['TLSADD']='TLSO ADDU\n'
        else:
            self.RefmacParams['TLS']=''
            self.RefmacParams['TLSIN']=''
            self.RefmacParams['TLSOUT']=''
            self.RefmacParams['TLSADD']=''
        return self.RefmacParams

    def NCSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['NCS']='NCSR LOCAL\n'
        else:
            self.RefmacParams['NCS']=''
        return self.RefmacParams

    def ChooseBfacRefinement(self,widget):
        if widget.get_active_text()=='isotropic':
            self.RefmacParams['BREF']='    bref ISOT\n'
        if widget.get_active_text()=='anisotropic':
            self.RefmacParams['BREF']='    bref ANIS\n'
        return self.RefmacParams

    def on_key_release_Ncycles(self, widget, event):
        print widget.get_text()
        self.RefmacParams['NCYCLES'] = widget.get_text()
        return self.RefmacParams

    def on_key_release_MATRIX_WEIGHT(self, widget, event):
        self.RefmacParams['MATRIX_WEIGHT'] = widget.get_text()
        return self.RefmacParams

    def TWINCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TWIN']='TWIN\n'
        else:
            self.RefmacParams['TWIN']=''
        return self.RefmacParams

    def OK(self,widget):
        self.window.destroy()


    def ParamsFromPreviousCycle(self,Serial):

        RefmacParams={ 'HKLIN': '', 'HKLOUT': '',
                       'XYZIN': '', 'XYZOUT': '',
                       'LIBIN': '', 'LIBOUT': '',
                       'TLSIN': '', 'TLSOUT': '',
                       'TLSADD': '',
                       'NCYCLES': '10',
                       'MATRIX_WEIGHT': 'AUTO',
                       'BREF':   '    bref ISOT\n',
                       'TLS':    '',
                       'NCS':    '',
                       'TWIN':   ''    }

        if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
            for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
                if line.startswith('refi tlsc'):
                    RefmacParams['TLS']=line
                if line.startswith('TLSO'):
                    RefmacParams['TLSADD']=line
                if line.startswith('NCSR LOCAL'):
                    RefmacParams['NCS']=line
                if line.startswith('    bref '):
                    RefmacParams['BREF']=line
                if line.startswith('ncyc'):
                    RefmacParams['Ncycles'] = line.split()[1]
                if line.startswith('weight'):
                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
                if line.startswith('TWIN'):
                    RefmacParams['TWIN']=line
        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-restraints.refmac.params')):
            for line in open(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-restraints.refmac.params')):
                if 'refi tlsc' in line:
                    RefmacParams['TLS']=line
                if 'TLSO' in line:
                    RefmacParams['TLSADD']=line
                if 'NCSR LOCAL' in line:
                    RefmacParams['NCS']=line
                if 'bref' in line:
                    RefmacParams['BREF']=line
                if 'ncyc' in line:
                    RefmacParams['Ncycles'] = line.split()[1]
                if 'weight' in line:
                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
                if 'TWIN' in line:
                    RefmacParams['TWIN']=line

        return RefmacParams

    def GetRefinementHistory(self):
#        RefinementHistory=''
        RefinementCycle = []
        RcrystList=[]
        RfreeList=[]

        found = False
        for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
            if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
                    print item[item.rfind('_')+1:]
                    RefinementCycle.append(int(item[item.rfind('_')+1:]))
                    found = True
        if found:
            for cycle in sorted(RefinementCycle):
#            for cycle in RefinementCycle:
#                Rcryst=0
#                Rfree=0
#                LigandCC=0
                try:
                    found_Rcryst=False
                    found_Rfree=False
                    newestPDB = max(glob.iglob(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/refine_'+str(cycle)+'.pdb'), key=os.path.getctime)
                    for line in open(newestPDB):
                        if line.startswith('REMARK   3   R VALUE     (WORKING + TEST SET) :'):
                            Rcryst = line.split()[9]
                            RcrystList.append(float(Rcryst))
                            found_Rcryst=True
                        if line.startswith('REMARK   3   FREE R VALUE                     :'):
                            Rfree = line.split()[6]
                            RfreeList.append(float(Rfree))
                            found_Rfree=True
                    if not found_Rcryst:
                        RcrystList.append(0)
                    if not found_Rfree:
                        RfreeList.append(0)
#                    if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                        for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                                if line.startswith('|  LIG'): LigandCC = line.split()[6]
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
                except ValueError:
                    RcrystList.append(0)
                    RfreeList.append(0)
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
        else:
            RefinementCycle = [0]
            RcrystList=[0]
            RfreeList=[0]
        print RefinementCycle,RcrystList,RfreeList
        return(sorted(RefinementCycle),RcrystList,RfreeList)




class panddaRefine(object):

    def __init__(self,ProjectPath,xtalID,compoundID,datasource):
        self.ProjectPath = ProjectPath
        self.xtalID = xtalID
        self.compoundID = compoundID
        self.prefix = 'refine'
        self.datasource=datasource


    def make_covalent_link(self,covLinkAtomSpec,Logfile):
        residuesToModify = ['CYS','SER']

        atom1 = covLinkAtomSpec[1][5]
        atom2 = covLinkAtomSpec[2][5]
        residue_1 = covLinkAtomSpec[3]
        residue_2 = covLinkAtomSpec[4]

        if residue_2 in residuesToModify:
            bond_text = 'LINK: RES-NAME-1 %s FILE-1 %s_acedrg.cif ATOM-NAME-1  %s  RES-NAME-2 %s ATOM-NAME-2  %s' %(residue_1,self.compoundID,atom1,residue_2,atom2)
        else:
            bond_text = 'LINK: RES-NAME-1 %s FILE-1 %s_acedrg.cif ATOM-NAME-1  %s  RES-NAME-2 %s ATOM-NAME-2  %s' % (residue_2, self.compoundID, atom2, residue_1, atom1)

        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
        f = open('covalent_bond.txt','w')
        f.write(bond_text)
        f.close()

        # seems somewhat unncessary, but acedrg does not like some certain descriptions generated by phenix.elbow
        os.system('acedrg -c %s.cif -o %s_acedrg' %(self.compoundID,self.compoundID))

        os.system('acedrg -L covalent_bond.txt -o %s' %self.compoundID)

        if os.path.isfile('%s_link.cif' %self.compoundID):
            Logfile.insert('succefully created link file %s_link.cif' %self.compoundID)
            os.system('/bin/rm %s.cif' %self.compoundID)
            os.system('ln -s %s_link.cif %s.cif' %(self.compoundID,self.compoundID))
        else:
            Logfile.error('could not create linkfile; please check logs in %s/%s' %(self.ProjectPath,self.xtalID))




    def RunQuickRefine(self,Serial,RefmacParams,external_software,xce_logfile,refinementProtocol,covLinkAtomSpec):
        Logfile=XChemLog.updateLog(xce_logfile)
        Logfile.insert('preparing files for giant.quick_refine')
        # panddaSerial because giant.quick_refine writes Refine_0001 instead of Refine_1
        panddaSerial=(4-len(str(Serial)))*'0'+str(Serial)

        make_all_links = True
        add_links_line = ''

        if covLinkAtomSpec is not None:
            self.make_covalent_link(covLinkAtomSpec,Logfile)

        # first check if refinement is ongoing and exit if yes
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'REFINEMENT_IN_PROGRESS')):
#            coot.info_dialog('*** REFINEMENT IN PROGRESS ***')
            Logfile.insert('cannot start new refinement for %s: *** REFINEMENT IN PROGRESS ***' %self.xtalID)
            return None

        #######################################################
        # HKLIN & HKLOUT
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz')):
            RefmacParams['HKLIN']=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz')
        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
            RefmacParams['HKLIN']=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')
        else:
            Logfile.insert('%s: cannot find HKLIN for refinement; aborting...' %self.xtalID)
            return None

        #######################################################
        # LIBIN & LIBOUT
        found_cif=False
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.compoundID+'.cif')):
            found_cif=True
            RefmacParams['LIBIN']=os.path.join(self.ProjectPath,self.xtalID,self.compoundID+'.cif')
        if not found_cif:
        # this should actually not be necessary, but the following scenario can happen:
        # if a new data source is created from a file system, but smiles and compoundID where not updated;
        # so the ligand may still be in the structure, but since the compoundID is unknown to the datasource,
        # its restraints won't be read in and refmac will fail
            for file in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
                if file.endswith('.cif'):
                    RefmacParams['LIBIN']=file
                    break

        #######################################################
        # giant_merge_conformations
        Logfile.insert('trying to merge modified bound state with ground state')
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),self.xtalID+'-ensemble-model.pdb')):
            Logfile.insert('seems to be an initial refinement after pandda.export, no need to merge the conformations')
            os.chdir(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
            Logfile.insert('running giant.make_restraints %s:' %self.xtalID+'-ensemble-model.pdb')
#            os.system('giant.make_restraints %s' %self.xtalID+'-ensemble-model.pdb')
            cmd = (
                'export XChemExplorer_DIR="%s"\n' %os.getenv('XChemExplorer_DIR')+
                'source %s\n' %os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh\n') +
                'giant.make_restraints %s-ensemble-model.pdb' %self.xtalID
            )
            Logfile.insert(cmd+'\n')
            os.system(cmd)
        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'refine.split.ground-state.pdb')):
            Logfile.insert('found model of ground state: '+os.path.join(self.ProjectPath,self.xtalID,'refine.split.ground-state.pdb'))
            if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refine.modified.pdb')):
                Logfile.insert('found model of modified bound state')
                os.chdir(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
                ground_state=os.path.join(self.ProjectPath,self.xtalID,'refine.split.ground-state.pdb')
                bound_state='refine.modified.pdb'
                Logfile.insert('running giant.merge_conformations major=%s minor=%s' %(ground_state,bound_state))
                if os.getcwd().startswith('/dls'):
                    cmd = (
                    'export XChemExplorer_DIR="%s"\n' %os.getenv('XChemExplorer_DIR')+
                    'source %s\n' %os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh\n') +
                    'giant.merge_conformations major=%s minor=%s reset_all_occupancies=False options.major_occupancy=1.0 options.minor_occupancy=1.0' %(ground_state,bound_state)
                    )
                else:
                    cmd = (
                    'giant.merge_conformations major=%s minor=%s reset_all_occupancies=False options.major_occupancy=1.0 options.minor_occupancy=1.0' %(ground_state,bound_state)
                    )
                Logfile.insert(cmd+'\n')
                os.system(cmd)
                link_line = ''
                for line in open(bound_state):
                    if line.startswith('LINK'):
                        Logfile.insert('found LINK: ' + line[:-1])
                        link_line += line
                if link_line != '':
                    if os.path.isfile('multi-state-model.pdb'):
                        for line in open('multi-state-model.pdb'):
                            if line.startswith('CRYST'):
                                Logfile.insert('adding LINK lines to multi-state-model.pdb')
                                out = link_line + line
                            else:
                                out += line
                        Logfile.insert('writing updated multi-state-model.pdb')
                        f = open('multi-state-model.pdb','w')
                        f.write(out)
                        f.close()
                    else:
                        Logfile.error('cannot find multi-state-model.pdb')
            else:
                Logfile.error('cannot find modified version of bound state in %s' %os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
                return None
        else:
            if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refine.modified.pdb')):
                os.chdir(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
                Logfile.warning('%s: ground-state model does not exist, but refine.modified.pdb does exist' %self.xtalID)
                Logfile.warning('This may be a case where there are no differences between bound and ground state')
                Logfile.warning('creating symbolic link: ln -s refine.modified.pdb %s-ensemble-model.pdb' %self.xtalID)
                os.system('ln -s refine.modified.pdb %s-ensemble-model.pdb' %self.xtalID)
                # note: after first cycle of refinement, REFMAC will remove alternate conformer from the ligand
                #       i.e. need to link refine.pdb to refine.split.bound-state.pdb
                make_all_links = False
                add_links_line = 'ln -s refine.pdb refine.split.bound-state.pdb'
                Logfile.insert('trying to continue with refinement')
            else:
                Logfile.error('cannot find any suitable PDB file for refinement, aborting...')
                return None


        #######################################################
        # checking if input PDB files are present
        Logfile.insert('checking if input PDB files for REFMAC are present')
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),self.xtalID+'-ensemble-model.pdb')):
            RefmacParams['XYZIN']=os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),self.xtalID+'-ensemble-model.pdb')
        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-model.pdb')):
            RefmacParams['XYZIN']=os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-model.pdb')
        else:
            Logfile.error('cannot find multi-state-model.pdb in %s; aborting...' %os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
            return None


        #######################################################
        # checking if multi-state-restraints.refmac.params file is present
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-restraints.refmac.params')):
            # add REFMAC keywords to multi-state-restraints.refmac.params
            with open('multi-state-restraints.refmac.params','a') as refmacParams:
                refmacParams.write(RefmacParams['BREF']+'\n')
                refmacParams.write(RefmacParams['TLS']+'\n')
                refmacParams.write(RefmacParams['TWIN']+'\n')
                refmacParams.write('ncyc '+RefmacParams['NCYCLES']+'\n')
                if str(RefmacParams['MATRIX_WEIGHT']).lower() == 'auto':
                    refmacParams.write('weight AUTO' + '\n')
                else:
                    refmacParams.write('weight matrix '+str(RefmacParams['MATRIX_WEIGHT'])+'\n')
                refmacParams.write(RefmacParams['TLSADD']+'\n')
        else:
            Logfile.warning('cannot find multi-state-restraints.refmac.params in %s!' %os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
            try:
                os.chdir(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
                Logfile.insert('checking if %s-ensemble-model.pdb contains residue of type LIG, DRG, FRG, UNK or UNL' %self.xtalID)
                knowLigandIDs = ['LIG', 'DRG', 'FRG', 'UNK', 'UNL']
                ligandsInFile = pdbtools(self.xtalID+'-ensemble-model.pdb').find_ligands()
                found_lig = False
                for lig in ligandsInFile:
                    if lig[0] in knowLigandIDs:
                        Logfile.insert('found ligand of type: ' + lig[0])
                        found_lig = True
                if found_lig:
                    Logfile.warning('giant.make_restraints was not able to create multi-state-restraints.refmac.params. ' +
                                    'Something may have gone wrong, but it could be that ligand binding did not lead to ' +
                                    'displacement of water molecules or rearrangement of protein side-chains. ' +
                                    'Hence, there is no difference between the bound-state and the ground-state. ' +
                                    'We will create an empty multi-state-restraints.refmac.params which may contain ' +
                                    'additional REFMAC keywords and otherwise try to continue with refinement')
                    os.system('touch multi-state-restraints.refmac.params')
                else:
                    Logfile.error('%s-ensemble-model.pdb does not contain any modelled ligand; aborting refinement' %self.xtalID)
                    return None
            except OSError:
                Logfile.error('directory does not exisit: %s' %os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
                Logfile.error('aborting refinement...')
                return None

        #######################################################
        # we write 'REFINEMENT_IN_PROGRESS' immediately to avoid unncessary refinement
        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
        os.system('touch REFINEMENT_IN_PROGRESS')

        #######################################################
        # clean up!
        # and remove all files which will be re-created by current refinement cycle
        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
        files_to_remove = ( 'refine.pdb '
                            'refine.mtz '
                            'refine.split.bound-state.pdb '
                            'refine.split.ground-state.pdb '
                            'validation_summary.txt '
                            'validate_ligands.txt '
                            '2fofc.map '
                            'fofc.map '
                            'refine_molprobity.log' )
        os.system('/bin/rm %s' %files_to_remove)

        if external_software['qsub']:
            pbs_line='#PBS -joe -N XCE_refmac\n'
        else:
            pbs_line='\n'

        #######################################################
        # PANDDA validation @ spider plot
        spider_plot=''
        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')):
            if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
                pdb_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')
                mtz_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')
                pdb_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+str(panddaSerial),'refine_'+str(Serial)+'.pdb')
                mtz_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+str(panddaSerial),'refine_'+str(Serial)+'.mtz')
                spider_plot+='giant.score_model pdb1=%s mtz1=%s pdb2=%s mtz2=%s res_names=LIG,UNL,DRG,FRG\n' %(pdb_one,mtz_one,pdb_two,mtz_two)

        #######################################################
        # PHENIX stuff (if working at DLS)
        module_load=''
        if os.getcwd().startswith('/dls'):
            module_load='module load phenix\n'

        # 2017-07-20: for the time being this will explicitly source pandda since version 0.2 really only works at DLS
        source =''
        if 'bash' in os.getenv('SHELL'):
            source = (
                'export XChemExplorer_DIR="'+os.getenv('XChemExplorer_DIR')+'"\n'
                '\n'
                'source %s\n' %os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh\n')
            )
        elif 'csh' in os.getenv('SHELL'):
            source = (
                'setenv XChemExplorer_DIR '+os.getenv('XChemExplorer_DIR')+'\n'
                '\n'
                'source %s\n' %os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-csh\n')
            )


        if refinementProtocol=='pandda_refmac':
            refinementProgram='refmac'
            refinementParams=os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-restraints.refmac.params')
            mapCalculation = (
                'fft hklin refine.mtz mapout 2fofc.map << EOF\n'
                'labin F1=FWT PHI=PHWT\n'
                'EOF\n'
                '\n'
                'fft hklin refine.mtz mapout fofc.map << EOF\n'
                'labin F1=DELFWT PHI=PHDELWT\n'
                'EOF\n'   )
        elif refinementProtocol=='pandda_phenix':

            if os.getcwd().startswith('/dls'):
                module_load = 'module load phenix/1.13\n'

            refinementProgram='phenix'
            refinementParams=os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'multi-state-restraints.phenix.params')
            mapCalculation = (
                'fft hklin refine.mtz mapout 2fofc.map << EOF\n'
                'labin F1=2FOFCWT PHI=PH2FOFCWT\n'
                'EOF\n'
                '\n'
                'fft hklin refine.mtz mapout fofc.map << EOF\n'
                'labin F1=FOFCWT PHI=PHFOFCWT\n'
                'EOF\n'   )

        if make_all_links:
            add_links_line = (
            'ln -s Refine_%s/refine_%s.split.bound-state.pdb ./refine.split.bound-state.pdb\n' %(panddaSerial,Serial)+
            'ln -s Refine_%s/refine_%s.split.ground-state.pdb ./refine.split.ground-state.pdb\n' %(panddaSerial,Serial)
#            'ln -s Refine_%s/refine_%s.output.bound-state.pdb ./refine.output.bound-state.pdb\n' %(panddaSerial,Serial)+
#            'ln -s Refine_%s/refine_%s.output.ground-state.pdb ./refine.output.ground-state.pdb\n' %(panddaSerial,Serial)
            )


        refmacCmds = (
            '#!'+os.getenv('SHELL')+'\n'
            +pbs_line+
            '\n'
            + module_load +
            '\n'
            +source+
            'cd '+self.ProjectPath+'/'+self.xtalID+'\n'
            '\n'
            '$CCP4/bin/ccp4-python $XChemExplorer_DIR/helpers/update_status_flag.py %s %s %s %s\n' %(self.datasource,self.xtalID,'RefinementStatus','running') +
            '\n'
            'giant.quick_refine'
            ' input.pdb=%s' %RefmacParams['XYZIN']+
            ' mtz=%s' %RefmacParams['HKLIN']+
            ' cif=%s' %RefmacParams['LIBIN']+
            ' program=%s' %refinementProgram +
            ' params=%s' %refinementParams+
            " dir_prefix='Refine_'"
            " out_prefix='refine_%s'" %str(Serial)+
            " split_conformations='False'"
            '\n'
            'cd '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(panddaSerial)+'\n'
            
            'ln -s '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(panddaSerial)+'/refine_'+str(Serial)+'_001.pdb '
            +self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(panddaSerial)+'/refine_'+str(Serial)+'.pdb' +'\n'
             
            'ln -s '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(panddaSerial)+'/refine_'+str(Serial)+'_001.mtz '
            +self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(panddaSerial)+'/refine_'+str(Serial)+'.mtz' +'\n'

            'giant.split_conformations'
            " input.pdb='refine_%s.pdb'" %str(Serial)+
            ' reset_occupancies=False'
            ' suffix_prefix=split'
            '\n'
            'giant.split_conformations'
            " input.pdb='refine_%s.pdb'" %str(Serial)+
            ' reset_occupancies=True'
            ' suffix_prefix=output '
            '\n'
            +spider_plot+
            '\n'
            'phenix.molprobity refine_%s.pdb refine_%s.mtz\n' %(Serial,Serial)+
            '/bin/mv molprobity.out refine_molprobity.log\n'
            'module load phenix\n'
            'mmtbx.validate_ligands refine_%s.pdb refine_%s.mtz LIG > validate_ligands.txt\n' %(Serial,Serial)+
            'cd '+self.ProjectPath+'/'+self.xtalID+'\n'
            '\n'
            'ln -s Refine_%s/validate_ligands.txt .\n' %panddaSerial+
            'ln -s Refine_%s/refine_molprobity.log .\n' %panddaSerial+
            '\n'
            + add_links_line +
            '\n'
            'mmtbx.validation_summary refine.pdb > validation_summary.txt\n'
            '\n'
            + mapCalculation +
            '\n'
            '$CCP4/bin/ccp4-python '+os.path.join(os.getenv('XChemExplorer_DIR'),'helpers','update_data_source_after_refinement.py')+
            ' %s %s %s %s\n' %(self.datasource,self.xtalID,self.ProjectPath,os.path.join(self.ProjectPath,self.xtalID,'Refine_'+str(panddaSerial)))+
            '\n'
            '/bin/rm %s/%s/REFINEMENT_IN_PROGRESS\n' %(self.ProjectPath,self.xtalID)+
            '\n'
           )

        Logfile.insert('writing refinement shell script to'+os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refmac.csh'))
        cmd = open(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial),'refmac.csh'),'w')
        cmd.write(refmacCmds)
        cmd.close()

        os.chdir(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
#        os.system('ssh artemis "cd %s/%s/Refine_%s; qsub refmac.csh"' %(self.ProjectPath,self.xtalID,Serial))
        Logfile.insert('changing directory to %s' %(os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial))))

        if external_software['qsub']:
            Logfile.insert('starting refinement on cluster')
            os.system('qsub -P labxchem refmac.csh')
        elif external_software['qsub_remote'] != '':
            Logfile.insert('starting refinement on remote cluster')
            remote_command=external_software['qsub_remote'].replace('qsub','cd %s; qsub' %os.path.join(self.ProjectPath,self.xtalID,'cootOut','Refine_'+str(Serial)))
            os.system('%s -P labxchem refmac.csh' %remote_command)
            print '%s -P labxchem refmac.csh' %remote_command
        else:
            Logfile.insert('changing permission of refmac.csh: chmod +x refmac.csh')
            os.system('chmod +x refmac.csh')
            Logfile.insert('starting refinement on local machine')
            os.system('./refmac.csh &')

#            if '/work/' in os.getcwd():
#            os.system('ssh artemis "cd %s/%s/Refine_%s; qsub refmac.csh"' %(self.ProjectPath,self.xtalID,Serial))
#            else:
#                os.system('./refmac.csh &')




    def RefinementParams(self,RefmacParams):
        self.RefmacParams=RefmacParams
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", gtk.main_quit)
        self.window.set_border_width(10)
        self.window.set_title("Refmac Parameters")
        self.vbox = gtk.VBox()

        self.hbox1=gtk.HBox()
        self.hbox1.add(gtk.Label('Refine'))
        self.cb = gtk.combo_box_new_text()
        self.cb.connect("changed", self.ChooseBfacRefinement)
        for item in ['isotropic','anisotropic']:
            self.cb.append_text(item)
        if 'ISOT' in self.RefmacParams['BREF']:
            self.cb.set_active(0)
        if 'ANIS' in self.RefmacParams['BREF']:
            self.cb.set_active(1)
        self.hbox1.add(self.cb)
        self.hbox1.add(gtk.Label('temperature factors'))
        self.vbox.add(self.hbox1)

        self.hbox2=gtk.HBox()
        self.hbox2.add(gtk.Label('Number of Cycles: '))
        self.Ncycles=gtk.Entry()
        self.Ncycles.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.Ncycles.connect("key-release-event", self.on_key_release_Ncycles)
        self.Ncycles.set_text(self.RefmacParams['NCYCLES'])
        self.hbox2.add(self.Ncycles)
        self.vbox.add(self.hbox2)

        self.hbox3=gtk.HBox()
        self.hbox3.add(gtk.Label('MATRIX WEIGHT: '))
        self.MATRIX_WEIGHT=gtk.Entry()
        self.MATRIX_WEIGHT.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.MATRIX_WEIGHT.connect("key-release-event", self.on_key_release_MATRIX_WEIGHT)
        self.MATRIX_WEIGHT.set_text(self.RefmacParams['MATRIX_WEIGHT'])
        self.hbox3.add(self.MATRIX_WEIGHT)
        self.vbox.add(self.hbox3)

        self.TLS = gtk.CheckButton('TLS (find TLS groups with phenix.find_tls_groups)')
        self.TLS.connect("toggled", self.TLSCallback)
        if self.RefmacParams['TLS']=='refi tlsc 10\n': self.TLS.set_active(True)
        self.vbox.pack_start(self.TLS,False)

        self.NCS = gtk.CheckButton('NCS (if applicable')
        self.NCS.connect("toggled", self.NCSCallback)
        if self.RefmacParams['NCS']=='NCSR LOCAL\n': self.NCS.set_active(True)
        self.vbox.pack_start(self.NCS,False)

        self.TWIN = gtk.CheckButton('Twin?')
        self.TWIN.connect("toggled", self.TWINCallback)
        if self.RefmacParams['TWIN']=='TWIN\n': self.TWIN.set_active(True)
        self.vbox.pack_start(self.TWIN,False)

        self.OKbutton = gtk.Button(label="OK")
        self.OKbutton.connect("clicked",self.OK)
        self.vbox.add(self.OKbutton)

        self.window.add(self.vbox)
        self.window.show_all()
        return self.RefmacParams


    def TLSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TLS']='refi tlsc 10\n'
            self.RefmacParams['TLSIN']='refmac.tls\n'
            self.RefmacParams['TLSOUT']='out.tls\n'
            self.RefmacParams['TLSADD']='TLSO ADDU\n'
        else:
            self.RefmacParams['TLS']=''
            self.RefmacParams['TLSIN']=''
            self.RefmacParams['TLSOUT']=''
            self.RefmacParams['TLSADD']=''
        return self.RefmacParams

    def NCSCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['NCS']='NCSR LOCAL\n'
        else:
            self.RefmacParams['NCS']=''
        return self.RefmacParams

    def ChooseBfacRefinement(self,widget):
        if widget.get_active_text()=='isotropic':
            self.RefmacParams['BREF']='    bref ISOT\n'
        if widget.get_active_text()=='anisotropic':
            self.RefmacParams['BREF']='    bref ANIS\n'
        return self.RefmacParams

    def on_key_release_Ncycles(self, widget, event):
        print widget.get_text()
        self.RefmacParams['NCYCLES'] = widget.get_text()
        return self.RefmacParams

    def on_key_release_MATRIX_WEIGHT(self, widget, event):
        self.RefmacParams['MATRIX_WEIGHT'] = widget.get_text()
        return self.RefmacParams

    def TWINCallback(self, widget):
        if widget.get_active():
            self.RefmacParams['TWIN']='TWIN\n'
        else:
            self.RefmacParams['TWIN']=''
        return self.RefmacParams

    def OK(self,widget):
        self.window.destroy()


    def ParamsFromPreviousCycle(self,Serial):

        RefmacParams={ 'HKLIN': '', 'HKLOUT': '',
                       'XYZIN': '', 'XYZOUT': '',
                       'LIBIN': '', 'LIBOUT': '',
                       'TLSIN': '', 'TLSOUT': '',
                       'TLSADD': '',
                       'NCYCLES': '10',
                       'MATRIX_WEIGHT': 'AUTO',
                       'BREF':   '    bref ISOT\n',
                       'TLS':    '',
                       'NCS':    '',
                       'TWIN':   ''    }

        if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
            for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
                if line.startswith('refi tlsc'):
                    RefmacParams['TLS']=line
                if line.startswith('TLSO'):
                    RefmacParams['TLSADD']=line
                if line.startswith('NCSR LOCAL'):
                    RefmacParams['NCS']=line
                if line.startswith('    bref '):
                    RefmacParams['BREF']=line
                if line.startswith('ncyc'):
                    RefmacParams['Ncycles'] = line.split()[1]
                if line.startswith('weight'):
                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
                if line.startswith('TWIN'):
                    RefmacParams['TWIN']=line

        return RefmacParams

    def GetRefinementHistory(self):
#        RefinementHistory=''
        RefinementCycle = []
        RcrystList=[]
        RfreeList=[]

        found = False
        for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
            if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
                    print item[item.rfind('_')+1:]
                    RefinementCycle.append(int(item[item.rfind('_')+1:]))
                    found = True
        if found:
            for cycle in sorted(RefinementCycle):
#            for cycle in RefinementCycle:
#                Rcryst=0
#                Rfree=0
#                LigandCC=0
                try:
                    found_Rcryst=False
                    found_Rfree=False
                    newestPDB = max(glob.iglob(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/refine_'+str(cycle)+'.pdb'), key=os.path.getctime)
                    for line in open(newestPDB):
                        if line.startswith('REMARK   3   R VALUE     (WORKING + TEST SET) :'):
                            Rcryst = line.split()[9]
                            RcrystList.append(float(Rcryst))
                            found_Rcryst=True
                        if line.startswith('REMARK   3   FREE R VALUE                     :'):
                            Rfree = line.split()[6]
                            RfreeList.append(float(Rfree))
                            found_Rfree=True
                    if not found_Rcryst:
                        RcrystList.append(0)
                    if not found_Rfree:
                        RfreeList.append(0)
#                    if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                        for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
#                                if line.startswith('|  LIG'): LigandCC = line.split()[6]
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
                except ValueError:
                    RcrystList.append(0)
                    RfreeList.append(0)
#                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
        else:
            RefinementCycle = [0]
            RcrystList=[0]
            RfreeList=[0]
        print RefinementCycle,RcrystList,RfreeList
        return(sorted(RefinementCycle),RcrystList,RfreeList)


#class RefineOld(object):
#
#    def __init__(self,ProjectPath,xtalID,compoundID,datasource):
#        self.ProjectPath = ProjectPath
#        self.xtalID = xtalID
#        self.compoundID = compoundID
#        self.prefix = 'refine'
#        self.datasource=datasource
#
#    def GetSerial(self):
#        # check if there were already previous refinements
#        # if no: create a folder Refine_1
#        # if yes: create a folder Refine_<max+1>
#        temp = []
#        found = 0
#        if os.path.isdir(os.path.join(self.ProjectPath,self.xtalID)):
#            for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
#                if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
#                        print int(item[item.rfind('_')+1:])
#                        temp.append(int(item[item.rfind('_')+1:]))
#                        found = 1
#        if found:
#            Serial = max(temp) + 1
#        else:
#            Serial=1
#        return Serial
#
#
#    def RunRefmac(self,Serial,RefmacParams,external_software,xce_logfile):
#        Logfile=XChemLog.updateLog(xce_logfile)
#        Serial=str(Serial)
#
#        # first check if refinement is ongoing and exit if yes
#        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'REFINEMENT_IN_PROGRESS')):
##            coot.info_dialog('*** REFINEMENT IN PROGRESS ***')
#            Logfile.insert('cannot start new refinement for %s: *** REFINEMENT IN PROGRESS ***' %self.xtalID)
#            return None
#
#        #######################################################
#        # HKLIN & HKLOUT
#        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz')):
#            RefmacParams['HKLIN']='HKLIN '+os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'.free.mtz \\\n')
#        elif os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
#            RefmacParams['HKLIN']='HKLIN '+os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz \\\n')
#        else:
#            Logfile.insert('%s: cannot find HKLIN for refinement; aborting...' %self.xtalID)
#            return None
#        RefmacParams['HKLOUT']='HKLOUT '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.mtz \\\n')
#
#        #######################################################
#        # XYZIN & XYZOUT
#        RefmacParams['XYZIN']='XYZIN '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'in.pdb \\\n')
#        RefmacParams['XYZOUT']='XYZOUT '+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.pdb \\\n')
#
#        #######################################################
#        # LIBIN & LIBOUT
#        found_cif=False
#        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.compoundID+'.cif')):
#            found_cif=True
#            # in cases where multiple liagnds are present (e.g. NOG, ATP) the user for now needs to put
#            # the respective dictionary into the xtalID folder
#            # need to think of a better mechanism in the future
#            additional_cif=False
#            additional_cif_file=''
#            for file in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
#                if file.endswith('.cif'):
#                    if self.compoundID not in file:
#                        additional_cif_file=file
##                        additional_cif=True   <- should be true, but need to check this part of the code! 16/11/2016
#                        additional_cif=False
#            if additional_cif:
#                Cmds = (
#                    '#!'+os.getenv('SHELL')+'\n'
#                    '\n'
#                    '$CCP4/bin/libcheck << eof \n'
#                    '_Y\n'
#                    '_FILE_L '+os.path.join(self.ProjectPath,self.xtalID,self.compoundID+'.cif')+'\n'
#                    '_FILE_L2 '+additional_cif_file+'\n'
#                    '_FILE_O '+os.path.join(self.ProjectPath,self.xtalID,'combined_cif')+'\n'
#                    '_END\n'
#                    'eof\n'
#                    )
#                os.chdir(os.path.join(self.ProjectPath,self.xtalID))
#                print Cmds
#                os.system(Cmds)
#                RefmacParams['LIBIN']='LIBIN '+self.ProjectPath+'/'+self.xtalID+'/combined_cif.lib \\\n'
#            else:
#                RefmacParams['LIBIN']='LIBIN '+self.ProjectPath+'/'+self.xtalID+'/'+self.compoundID+'.cif \\\n'
#            RefmacParams['LIBOUT']='LIBOUT '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refine_'+Serial+'.cif \\\n'
#        if not found_cif:
#        # this should actually not be necessary, but the following scenario can happen:
#        # if a new data source is created from a file system, but smiles and compoundID where not updated;
#        # so the ligand may still be in the structure, but since the compoundID is unknown to the datasource,
#        # its restraints won't be read in and refmac will fail
#            for file in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
#                if file.endswith('.cif'):
#                    RefmacParams['LIBIN']='LIBIN '+file+' \\\n'
#                    RefmacParams['LIBOUT']='LIBOUT '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refine_'+Serial+'.cif \\\n'
#                    break
#
#        #######################################################
#        # TLSIN & TLSOUT
#        findTLS='\n'
#        TLSphenix=''
#        if RefmacParams['TLS'].startswith('refi'):
#            if external_software['phenix.find_tls_groups']:
#                findTLS=os.path.join(os.getenv('XChemExplorer_DIR'),'helpers','phenix_find_TLS_groups.py')+' in.pdb\n'
#                RefmacParams['TLSIN']='TLSIN '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refmac.tls \\\n'
#                RefmacParams['TLSOUT']='TLSOUT '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'/refine.tls \\\n'
#                TLSphenix=' phenix.tls '
#            else:
#                RefmacParams['TLS']='\n'
#
#
##        #######################################################
##        # create folder for new refinement cycle
##        os.mkdir(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
##
##        #######################################################
##        # write PDB file
##        # now take protein pdb file and write it to newly create Refine_<serial> folder
##        # note: the user has to make sure that the ligand file was merged into main file
##        for item in coot_utils_XChem.molecule_number_list():
##            if coot.molecule_name(item).endswith(self.prefix+'.pdb'):
##                coot.write_pdb_file(item,os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'in.pdb'))
#
#        #######################################################
#        # PANDDAs stuff
#        # only use occupancy refinement if EVENT map is present
#        occupancy_refinement=''
#        if external_software['giant.create_occupancy_params']:
#            os.chdir(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
#            cmd = ( '#!'+os.getenv('SHELL')+'\n'
#                    'export XChemExplorer_DIR="'+os.getenv('XChemExplorer_DIR')+'"\n'
#                    'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','xce.setup-sh')+'\n'
#                    'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh')+'\n'
#                    "giant.create_occupancy_params pdb=in.pdb refmac_occ_out='refmac_refine.params'\n"  )
##            os.system("giant.create_occupancy_params pdb=in.pdb refmac_occ_out='refmac_refine.params'")
##            os.system(cmd)
#            print "==> XCE: running giant.create_occupancy_params pdb=in.pdb refmac_occ_out='refmac_refine.params'"
#            os.system("giant.create_occupancy_params pdb=in.pdb refmac_occ_out='refmac_refine.params'")
#            # quick fix for the moment; need to talk to Nick since this should not be necessary
#            try:
#                params_file = fileinput.input('refmac_refine.params',inplace=True)
#                for line in params_file:
#                    if 'incomplete' in line:
#                        line=line.replace('incomplete','complete')
#                        print line,
##                elif 'occupancy refine' in line:
##                    line=line.replace('occupancy refine','occupancy refine ncycle 10\noccupancy refine')
##                    print line,
#                    else:
#                        print line,
#                params_file.close()
#            except OSError:
#                # this may happen in case giant.create_occupancy_params did not produce a params output file
#                pass
#
#            print '==> XCE: waiting 5 seconds for giant.create_occupancy_params to finish...'
#            time.sleep(5)
#            print '==> XCE: done!'
#
#        print '==> XCE: assembling refmac.csh'
#
#        create_bound_conformation=''
#        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refmac_refine.params')):
#            occupancy_refinement='@refmac_refine.params\n'
#            create_bound_conformation="/bin/rm *bound.pdb\ngiant.strip_conformations pdb=refine.pdb suffix='.bound.pdb'\n"
#
#        #######################################################
#        # we write 'REFINEMENT_IN_PROGRESS' immediately to avoid unncessary refiment
#        os.chdir(os.path.join(self.ProjectPath,self.xtalID))
#        os.system('touch REFINEMENT_IN_PROGRESS')
#
#        #######################################################
#        # clean up!
#        # and remove all files which will be re-created by current refinement cycle
#        os.system('/bin/rm refine.pdb refine.mtz validation_summary.txt validate_ligands.txt 2fofc.map fofc.map refine_molprobity.log')
#
#        if external_software['qsub']:
#            pbs_line='#PBS -joe -N XCE_refmac\n'
#        else:
#            pbs_line='\n'
#
#        #######################################################
#        # weight
#        if str(RefmacParams['MATRIX_WEIGHT']).lower() == 'auto':
#            weight='weight AUTO\n'
#        else:
#            weight='weight matrix '+str(RefmacParams['MATRIX_WEIGHT'])+'\n'
#
#        #######################################################
#        # PANDDA validation @ spider plot
#        spider_plot=''
#        if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')):
#            if os.path.isfile(os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')):
#                pdb_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-ensemble-model.pdb')
#                mtz_two=os.path.join(self.ProjectPath,self.xtalID,self.xtalID+'-pandda-input.mtz')
#                pdb_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.pdb')
#                mtz_one=os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refine_'+Serial+'.mtz')
#                spider_plot='$CCP4/bin/ccp4-python $XChemExplorer_DIR/helpers/resort_ligand_atoms.py %s %s\n\n' %(pdb_two,pdb_one)
#                spider_plot+='giant.score_model pdb1=%s mtz1=%s pdb2=%s mtz2=%s res_names=LIG,UNL,DRG,FRG\n' %(pdb_one,mtz_one,pdb_two,mtz_two)
##                spider_plot='giant.score_model pdb1=%s mtz1=%s pdb2=%s mtz2=%s res_names=LIG,UNL,DRG,FRG\n' %(pdb_one,mtz_one,pdb_two,mtz_two)
#
#        #######################################################
#        # PHENIX stuff (if working at DLS)
#        module_load=''
#        if os.getcwd().startswith('/dls'):
#            module_load='module load phenix\n'
#
#        source =''
#        if 'bash' in os.getenv('SHELL'):
#            source = (
#                'export XChemExplorer_DIR="'+os.getenv('XChemExplorer_DIR')+'"\n'
#                '\n'
#                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','xce.setup-sh')+'\n'
#                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-sh')+'\n'   )
#        elif 'csh' in os.getenv('SHELL'):
#            source = (
#                'setenv XChemExplorer_DIR '+os.getenv('XChemExplorer_DIR')+'\n'
#                '\n'
#                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','xce.setup-csh')+'\n'
#                'source '+os.path.join(os.getenv('XChemExplorer_DIR'),'setup-scripts','pandda.setup-csh')+'\n'   )
#
#
#        refmacCmds = (
#            '#!'+os.getenv('SHELL')+'\n'
#            +pbs_line+
#            '\n'
#            + module_load +
#            '\n'
#            + source +
#            'cd '+self.ProjectPath+'/'+self.xtalID+'/Refine_'+Serial+'\n'
#            '\n'
#            '$CCP4/bin/ccp4-python $XChemExplorer_DIR/helpers/update_status_flag.py %s %s %s %s\n' %(self.datasource,self.xtalID,'RefinementStatus','running') +
#            '\n'
#            +findTLS+
#            'refmac5 '
#            +RefmacParams['HKLIN']
#            +RefmacParams['HKLOUT']
#            +RefmacParams['XYZIN']
#            +RefmacParams['XYZOUT']
#            +RefmacParams['LIBIN']
#            +RefmacParams['LIBOUT']
#            +RefmacParams['TLSIN']
#            +RefmacParams['TLSOUT']+
#            ' << EOF > refmac.log\n'
#            'make -\n'
#            '    hydrogen ALL -\n'
#            '    hout NO -\n'
#            '    peptide NO -\n'
#            '    cispeptide YES -\n'
#            '    ssbridge YES -\n'
#            '    symmetry YES -\n'
#            '    sugar YES -\n'
#            '    connectivity NO -\n'
#            '    link NO\n'
#            +RefmacParams['NCS']+
#            'refi -\n'
#            '    type REST -\n'
#            '    resi MLKF -\n'
#            '    meth CGMAT -\n'
#            +RefmacParams['BREF']
#            +RefmacParams['TLS']
#            +RefmacParams['TWIN']+
#            'ncyc '+RefmacParams['NCYCLES']+'\n'
#            'scal -\n'
#            '    type SIMP -\n'
#            '    LSSC -\n'
#            '    ANISO -\n'
#            '    EXPE\n'
#            +weight+
#            'solvent YES\n'
#            +occupancy_refinement+
#            'monitor MEDIUM -\n'
#            '    torsion 10.0 -\n'
#            '    distance 10.0 -\n'
#            '    angle 10.0 -\n'
#            '    plane 10.0 -\n'
#            '    chiral 10.0 -\n'
#            '    bfactor 10.0 -\n'
#            '    bsphere 10.0 -\n'
#            '    rbond 10.0 -\n'
#            '    ncsr 10.0\n'
#            'labin  FP=F SIGFP=SIGF FREE=FreeR_flag\n'
#            'labout  FC=FC FWT=FWT PHIC=PHIC PHWT=PHWT DELFWT=DELFWT PHDELWT=PHDELWT FOM=FOM\n'
#            +RefmacParams['TLSADD']+'\n'
#            'DNAME '+self.xtalID+'\n'
#            'END\n'
#            'EOF\n'
#            '\n'
#            +spider_plot+
#            '\n'
#            'phenix.molprobity refine_%s.pdb refine_%s.mtz\n' %(Serial,Serial)+
#            '/bin/mv molprobity.out refine_molprobity.log\n'
#            'mmtbx.validate_ligands refine_%s.pdb refine_%s.mtz LIG > validate_ligands.txt\n' %(Serial,Serial)+
#            'cd '+self.ProjectPath+'/'+self.xtalID+'\n'
#            '#ln -s %s/%s/Refine_%s/refine_%s.pdb refine.pdb\n' %(self.ProjectPath,self.xtalID,Serial,Serial)+
#            '#ln -s %s/%s/Refine_%s/refine_%s.mtz refine.mtz\n' %(self.ProjectPath,self.xtalID,Serial,Serial)+
#            'ln -s ./Refine_%s/refine_%s.pdb refine.pdb\n' %(Serial,Serial)+
#            'ln -s ./Refine_%s/refine_%s.mtz refine.mtz\n' %(Serial,Serial)+
#            '\n'
#            +create_bound_conformation+
#            '\n'
#            'ln -s Refine_%s/validate_ligands.txt .\n' %Serial+
#            'ln -s Refine_%s/refine_molprobity.log .\n' %Serial+
#            'mmtbx.validation_summary refine.pdb > validation_summary.txt\n'
#            '\n'
#            'fft hklin refine.mtz mapout 2fofc.map << EOF\n'
#            'labin F1=FWT PHI=PHWT\n'
#            'EOF\n'
#            '\n'
#            'fft hklin refine.mtz mapout fofc.map << EOF\n'
#            'labin F1=DELFWT PHI=PHDELWT\n'
#            'EOF\n'
#             '\n'
#            '$CCP4/bin/ccp4-python '+os.path.join(os.getenv('XChemExplorer_DIR'),'helpers','update_data_source_after_refinement.py')+
#            ' %s %s %s %s\n' %(self.datasource,self.xtalID,self.ProjectPath,os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))+
#            '\n'
#            '/bin/rm %s/%s/REFINEMENT_IN_PROGRESS\n' %(self.ProjectPath,self.xtalID)+
#            '\n'
#           )
#
#        Logfile.insert('writing refinement shell script to'+os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refmac.csh'))
#        cmd = open(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial,'refmac.csh'),'w')
#        cmd.write(refmacCmds)
#        cmd.close()
#
#        os.chdir(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
##        os.system('ssh artemis "cd %s/%s/Refine_%s; qsub refmac.csh"' %(self.ProjectPath,self.xtalID,Serial))
#        Logfile.insert('changing directory to %s' %(os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial)))
#        if external_software['qsub']:
#            Logfile.insert('starting refinement on cluster')
#            os.system('qsub -P labxchem refmac.csh')
#        elif external_software['qsub_remote'] != '':
#            Logfile.insert('starting refinement on remote cluster')
#            remote_command=external_software['qsub_remote'].replace('qsub','cd %s; qsub' %os.path.join(self.ProjectPath,self.xtalID,'Refine_'+Serial))
#            os.system('%s -P labxchem refmac.csh' %remote_command)
#            print '%s -P labxchem refmac.csh' %remote_command
#        else:
#            Logfile.insert('changing permission of refmac.csh: chmod +x refmac.csh')
#            os.system('chmod +x refmac.csh')
#            Logfile.insert('starting refinement on local machine')
#            os.system('./refmac.csh &')
##            if '/work/' in os.getcwd():
##            os.system('ssh artemis "cd %s/%s/Refine_%s; qsub refmac.csh"' %(self.ProjectPath,self.xtalID,Serial))
##            else:
##                os.system('./refmac.csh &')
#
#
#
#
#    def RefinementParams(self,RefmacParams):
#        self.RefmacParams=RefmacParams
#        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
#        self.window.connect("delete_event", gtk.main_quit)
#        self.window.set_border_width(10)
#        self.window.set_title("Refmac Parameters")
#        self.vbox = gtk.VBox()
#
#        self.hbox1=gtk.HBox()
#        self.hbox1.add(gtk.Label('Refine'))
#        self.cb = gtk.combo_box_new_text()
#        self.cb.connect("changed", self.ChooseBfacRefinement)
#        for item in ['isotropic','anisotropic']:
#            self.cb.append_text(item)
#        if 'ISOT' in self.RefmacParams['BREF']:
#            self.cb.set_active(0)
#        if 'ANIS' in self.RefmacParams['BREF']:
#            self.cb.set_active(1)
#        self.hbox1.add(self.cb)
#        self.hbox1.add(gtk.Label('temperature factors'))
#        self.vbox.add(self.hbox1)
#
#        self.hbox2=gtk.HBox()
#        self.hbox2.add(gtk.Label('Number of Cycles: '))
#        self.Ncycles=gtk.Entry()
#        self.Ncycles.add_events(gtk.gdk.KEY_RELEASE_MASK)
#        self.Ncycles.connect("key-release-event", self.on_key_release_Ncycles)
#        self.Ncycles.set_text(self.RefmacParams['NCYCLES'])
#        self.hbox2.add(self.Ncycles)
#        self.vbox.add(self.hbox2)
#
#        self.hbox3=gtk.HBox()
#        self.hbox3.add(gtk.Label('MATRIX WEIGHT: '))
#        self.MATRIX_WEIGHT=gtk.Entry()
#        self.MATRIX_WEIGHT.add_events(gtk.gdk.KEY_RELEASE_MASK)
#        self.MATRIX_WEIGHT.connect("key-release-event", self.on_key_release_MATRIX_WEIGHT)
#        self.MATRIX_WEIGHT.set_text(self.RefmacParams['MATRIX_WEIGHT'])
#        self.hbox3.add(self.MATRIX_WEIGHT)
#        self.vbox.add(self.hbox3)
#
#        self.TLS = gtk.CheckButton('TLS (find TLS groups with phenix.find_tls_groups)')
#        self.TLS.connect("toggled", self.TLSCallback)
#        if self.RefmacParams['TLS']=='refi tlsc 10\n': self.TLS.set_active(True)
#        self.vbox.pack_start(self.TLS,False)
#
#        self.NCS = gtk.CheckButton('NCS (if applicable')
#        self.NCS.connect("toggled", self.NCSCallback)
#        if self.RefmacParams['NCS']=='NCSR LOCAL\n': self.NCS.set_active(True)
#        self.vbox.pack_start(self.NCS,False)
#
#        self.TWIN = gtk.CheckButton('Twin?')
#        self.TWIN.connect("toggled", self.TWINCallback)
#        if self.RefmacParams['TWIN']=='TWIN\n': self.TWIN.set_active(True)
#        self.vbox.pack_start(self.TWIN,False)
#
#        self.OKbutton = gtk.Button(label="OK")
#        self.OKbutton.connect("clicked",self.OK)
#        self.vbox.add(self.OKbutton)
#
#        self.window.add(self.vbox)
#        self.window.show_all()
#        return self.RefmacParams
#
#
#    def TLSCallback(self, widget):
#        if widget.get_active():
#            self.RefmacParams['TLS']='refi tlsc 10\n'
#            self.RefmacParams['TLSIN']='refmac.tls\n'
#            self.RefmacParams['TLSOUT']='out.tls\n'
#            self.RefmacParams['TLSADD']='TLSO ADDU\n'
#        else:
#            self.RefmacParams['TLS']=''
#            self.RefmacParams['TLSIN']=''
#            self.RefmacParams['TLSOUT']=''
#            self.RefmacParams['TLSADD']=''
#        return self.RefmacParams
#
#    def NCSCallback(self, widget):
#        if widget.get_active():
#            self.RefmacParams['NCS']='NCSR LOCAL\n'
#        else:
#            self.RefmacParams['NCS']=''
#        return self.RefmacParams
#
#    def ChooseBfacRefinement(self,widget):
#        if widget.get_active_text()=='isotropic':
#            self.RefmacParams['BREF']='    bref ISOT\n'
#        if widget.get_active_text()=='anisotropic':
#            self.RefmacParams['BREF']='    bref ANIS\n'
#        return self.RefmacParams
#
#    def on_key_release_Ncycles(self, widget, event):
#        print widget.get_text()
#        self.RefmacParams['NCYCLES'] = widget.get_text()
#        return self.RefmacParams
#
#    def on_key_release_MATRIX_WEIGHT(self, widget, event):
#        self.RefmacParams['MATRIX_WEIGHT'] = widget.get_text()
#        return self.RefmacParams
#
#    def TWINCallback(self, widget):
#        if widget.get_active():
#            self.RefmacParams['TWIN']='TWIN\n'
#        else:
#            self.RefmacParams['TWIN']=''
#        return self.RefmacParams#
#
#    def OK(self,widget):
#        self.window.destroy()
#
#
#    def ParamsFromPreviousCycle(self,Serial):
#
#        RefmacParams={ 'HKLIN': '', 'HKLOUT': '',
#                       'XYZIN': '', 'XYZOUT': '',
#                       'LIBIN': '', 'LIBOUT': '',
#                       'TLSIN': '', 'TLSOUT': '',
#                       'TLSADD': '',
#                       'NCYCLES': '10',
#                       'MATRIX_WEIGHT': 'AUTO',
#                       'BREF':   '    bref ISOT\n',
#                       'TLS':    '',
#                       'NCS':    '',
#                       'TWIN':   ''    }
#
#        if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
#            for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(Serial)+'/refmac.csh'):
#                if line.startswith('refi tlsc'):
#                    RefmacParams['TLS']=line
#                if line.startswith('TLSO'):
#                    RefmacParams['TLSADD']=line
#                if line.startswith('NCSR LOCAL'):
#                    RefmacParams['NCS']=line
#                if line.startswith('    bref '):
#                    RefmacParams['BREF']=line
#                if line.startswith('ncyc'):
#                    RefmacParams['Ncycles'] = line.split()[1]
#                if line.startswith('weight'):
#                    RefmacParams['MATRIX_WEIGHT'] = line.split()[len(line.split())-1]
#                if line.startswith('TWIN'):
#                    RefmacParams['TWIN']=line
#
#        return RefmacParams
#
#    def GetRefinementHistory(self):
##        RefinementHistory=''
#        RefinementCycle = []
#        RcrystList=[]
#        RfreeList=[]
#
#        found = False
#        for item in glob.glob(os.path.join(self.ProjectPath,self.xtalID,'*')):
#            if item.startswith(os.path.join(self.ProjectPath,self.xtalID,'Refine_')):
#                    print item[item.rfind('_')+1:]
#                    RefinementCycle.append(int(item[item.rfind('_')+1:]))
#                    found = True
#        if found:
#            for cycle in sorted(RefinementCycle):
##            for cycle in RefinementCycle:
##                Rcryst=0
##                Rfree=0
##                LigandCC=0
#                try:
#                    found_Rcryst=False
#                    found_Rfree=False
#                    newestPDB = max(glob.iglob(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/refine_'+str(cycle)+'.pdb'), key=os.path.getctime)
#                    for line in open(newestPDB):
#                        if line.startswith('REMARK   3   R VALUE     (WORKING + TEST SET) :'):
#                            Rcryst = line.split()[9]
#                            RcrystList.append(float(Rcryst))
#                            found_Rcryst=True
#                        if line.startswith('REMARK   3   FREE R VALUE                     :'):
#                            Rfree = line.split()[6]
#                            RfreeList.append(float(Rfree))
#                            found_Rfree=True
#                    if not found_Rcryst:
#                        RcrystList.append(0)
#                    if not found_Rfree:
#                        RfreeList.append(0)
##                    if os.path.isfile(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
##                        for line in open(self.ProjectPath+'/'+self.xtalID+'/Refine_'+str(cycle)+'/validate_ligands.txt'):
##                                if line.startswith('|  LIG'): LigandCC = line.split()[6]
##                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
#                except ValueError:
#                    RcrystList.append(0)
#                    RfreeList.append(0)
##                    RefinementHistory=RefinementHistory+str(cycle).rjust(10)+str(R).rjust(10)+str(Rfree).rjust(10)+str(LigandCC).rjust(10)+'\n'
#        else:
#            RefinementCycle = [0]
#            RcrystList=[0]
#            RfreeList=[0]
#        print RefinementCycle,RcrystList,RfreeList
#        return(sorted(RefinementCycle),RcrystList,RfreeList)
#

