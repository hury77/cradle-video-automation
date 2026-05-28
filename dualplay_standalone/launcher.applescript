property serverPID : ""

on run
	set resourcesFolder to POSIX path of (path to me) & "Contents/Resources/"
	set launchScript to resourcesFolder & "launch.sh"
	
	try
		-- Run the shell script in the background and capture its PID
		set serverPID to do shell script "bash " & quoted form of launchScript & " > /dev/null 2>&1 & echo $!"
	end try
end run

on idle
	return 5
end idle

on quit
	if serverPID is not "" then
		try
			do shell script "kill " & serverPID
		end try
	end if
	continue quit
end quit
