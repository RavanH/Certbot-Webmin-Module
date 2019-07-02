#!/usr/bin/perl

BEGIN { push(@INC, ".."); };
use WebminCore;

require 'certbot-lib.pl';

foreign_require('webmin', 'webmin-lib.pl');
foreign_require('software', 'software-lib.pl');
foreign_require('apache', 'apache-lib.pl');

sub setup_checks{

	#check for GeoServer Apache config
	my @pkg_names;
	my %osinfo = webmin::detect_operating_system();
	if(	( $osinfo{'real_os_type'} =~ /centos/i) or	#CentOS
		($osinfo{'real_os_type'} =~ /fedora/i)	or  #Fedora
		($osinfo{'real_os_type'} =~ /scientific/i)	){
			@pkg_names = ('certbot', 'mod_ssl', 'openssl', 'python2-certbot-apache');

			if( $osinfo{'real_os_type'} =~ /centos/i){	#CentOS
				@pinfo = software::package_info('epel-release', undef, );
				if(!@pinfo){
					print "<p>Warning: certbot needs epel-release. Install it manually or ".
							"<a href='../package-updates/update.cgi?mode=new&source=3&u=epel-release&redir=%2E%2E%2Fcertbot%2Fsetup.cgi&redirdesc=Certbot Setup'>click here</a> to have it downloaded and installed.</p>";
				}
			}

	}elsif( ($osinfo{'real_os_type'} =~ /ubuntu/i) or
			($osinfo{'real_os_type'} =~ /debian/i) 	){	#ubuntu or debian
			@pkg_names = ('letsencrypt', 'python-certbot-apache');

			#add Certbot repo
			my %lsb_rel;
			read_env_file('/etc/lsb-release', \%lsb_rel);
			if(! -f "/etc/apt/sources.list.d/certbot-ubuntu-certbot-$lsb_rel{'DISTRIB_CODENAME'}.list"){
				print "<p>Warning: ppa:certbot/certbot is not installed. Install it manually or ".
						"<a href='setup.cgi?mode=certbot&return=%2E%2E%2Fcertbot%2F&returndesc=Certbot&caller=certbot'>here</a></p>";
			}
	}

	foreach my $pkg_name (@pkg_names){
		my @pinfo = software::package_info($pkg_name);
		if(!@pinfo){
			print "<p>Warning: $pkg_name package is not installed. Install it manually or ".
				  "<a href='../package-updates/update.cgi?mode=new&source=3&u=$pkg_name&redir=%2E%2E%2Fcertbot%2Fsetup.cgi&redirdesc=Certbot Setup'>click here</a> to have it downloaded and installed.</p>";
		}
	}

	#save letsencrypt_cmd to Webmin config
	if(!$webmin::config{'letsencrypt_cmd'}){
		my $le_cmd = get_certbot_cmd();
		if($le_cmd ne 'not-installed'){
			$webmin::config{'letsencrypt_cmd'} = $le_cmd;
			printf "Updated Webmin config with letsencrypt_cmd=".$le_cmd."</br>";
			save_module_config(\%webmin::config, 'webmin');
		}else{
			print 'Warning: letsencrypt command is missing. You won\'t be able to create certificates from "Lets Encrypt" form<br>';
		}
	}

	#enable SSL in apache
	if( ($osinfo{'real_os_type'} =~ /ubuntu/i) or
					($osinfo{'real_os_type'} =~ /debian/i) 	){	#ubuntu or debian

		if(! -f '/etc/apache2/mods-enabled/ssl.load'){
			&execute_command('a2enmod ssl');
		}

		if(! -f '/etc/apache2/sites-enabled/default-ssl.conf'){
			&execute_command('a2ensite default-ssl');
			print "Apache SSL configuration updated. Restarting...<br>";
			my $err = apache::restart_apache();
			if($err){
				print "Apache restart failed!: $err<br>";
			}
		}
	}

	if(! -d '/etc/letsencrypt/accounts'){
		printf '<p>Info: No account registered for Lets Encrypt. After settings all required options, register '.
				"<a href='setup.cgi?mode=register_form&return=%2E%2E%2Fcertbot%2F&returndesc=Certbot&caller=certbot'>here</a></p>";
	}

	print '<p>If you don\'t see any warning above, you can remove setup mode from '.
		  "<a href='setup.cgi?mode=cleanup&return=%2E%2E%2Fcertbot%2F&returndesc=Certbot&caller=certbot'>here</a></p>";
}

sub register_form(){
	print &ui_form_start("setup.cgi?mode=register_account", "post");
	print $text{'register_desc'}.'<br><br>';

	print &ui_table_start($text{'register_tbl_ttl'}, "width=100%", 2);
		print &ui_table_row($text{'agree-tos'}." (--agree-tos)", &ui_yesno_radio('agree-tos', 'false', 'true', 'false'), 2);
		print &ui_table_row($text{'eff-email'}." (--eff-email)", &ui_yesno_radio('eff-email', 'false', 'true', 'false'), 2);
		print &ui_table_row($text{'email'}." (--email)", &ui_textbox('email', '', 20), 2);
	print &ui_table_end();

	print &ui_form_end([ [ "", $text{'setup_register'} ] ]);
}

sub register_account(){
	if(!$in{'email'}){
		error("Error: No email specified!");
	}elsif($in{'agree-tos'} eq 'no'){
		error("Error: You have to agree with Let's Encrypt Terms Of Use!");
	}else{
		my $cmd = 'certbot register --agree-tos --email '.$in{'email'};
		$cmd .= ($in{'eff-email'} eq 'true') ? ' --eff-email' : ' --no-eff-email';
		$cmd .= ' 2>&1';	#output goes to stderr!

		my $out = &backquote_command($cmd);
		foreach my $line (split('\n', $out)){
			print &html_escape($line)."<br>";
		}

		#save the entered options
		my %opts_ini = ();
		read_file_cached('/etc/letsencrypt/cli.ini', \%opts_ini);
		$opts_ini{'email'} = $in{'email'};
		$opts_ini{'agree-tos'} = 'true';
		if($in{'eff-email'} eq 'yes'){
			$opts_ini{'eff-email'} = 'true';
		}else{
			$opts_ini{'no-eff-email'} = 'true';
		}
		write_file('/etc/letsencrypt/cli.ini', \%opts_ini);
	}
}

sub setup_certbot(){
	my %lsb_rel;
	read_env_file('/etc/lsb-release', \%lsb_rel);
	my @cmds = ('add-apt-repository -y ppa:certbot/certbot', 'apt-get -y update');
	foreach my $cmd (@cmds){
		&open_execute_command(CMD, $cmd, 1);
	  while(my $line = <CMD>) {
			$line = &html_escape($line);
			$line =~ s/\n/<br>/g;
			print $line;
		}
		close(CMD);
	}
}

#Remove all setup files
sub setup_cleanup{
	my $file = $module_root_directory.'/setup.cgi';
	print "Completing installation\n";
	&unlink_file($file);
}


&ui_print_header(undef, $text{'setup_title'}, "");

&ReadParse();

my $mode = $in{'mode'} || "checks";

if($mode eq "checks"){			setup_checks();		&ui_print_footer('', $text{'index_return'});	exit 0;
}elsif($mode eq "certbot"){	setup_certbot();	&ui_print_footer('', $text{'index_return'});	exit 0;
}elsif($mode eq "register_form"){			register_form();		&ui_print_footer('', $text{'index_return'});	exit 0;
}elsif($mode eq "register_account"){	register_account();	&ui_print_footer('', $text{'index_return'});	exit 0;
}elsif($mode eq "cleanup"){	setup_cleanup();	&ui_print_footer('', $text{'index_return'});	exit 0;
}else{
	print "Error: Invalid setup mode\n";
}

&ui_print_footer('setup.cgi', $text{'setup_title'});